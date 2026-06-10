"""
Slack notification logic. DB-aware; calls into app/slack.py for transport.

Three scheduled jobs (registered in app/sync.py):
  • notifications tick (every ~5 min): polls-open announcements + vote reminders
  • daily leaderboard (cron, fixed IST time)
  • match results are posted inline from the result-sync job (announce_match_result)

Every announcement is recorded in the sent_notifications table so a job that runs
repeatedly never reposts the same event. To avoid backfiring a backlog when the
bot first goes live, time-triggered events only fire within ANNOUNCE_WINDOW of
their trigger time.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from app.db import SessionLocal
from app.models import Match, Vote, User, Score, SentNotification
from app import slack

logger = logging.getLogger(__name__)

IST_OFFSET = timedelta(hours=5, minutes=30)
REMINDER_HOURS_BEFORE = int(os.getenv("SLACK_REMINDER_HOURS_BEFORE", "3"))
LEADERBOARD_HOUR_IST = int(os.getenv("SLACK_LEADERBOARD_HOUR_IST", "9"))
# A time-triggered event only fires if "now" is within this window past its trigger.
# Keeps the scheduler (every 5 min) from missing it, without replaying old events.
ANNOUNCE_WINDOW = timedelta(minutes=60)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ist_date_label(dt: datetime) -> str:
    return (dt + IST_OFFSET).strftime("%a, %b %d")


def leaderboard_cron_utc() -> tuple[int, int]:
    """The configured IST leaderboard hour, expressed as (hour, minute) UTC."""
    total = (LEADERBOARD_HOUR_IST * 60 - int(IST_OFFSET.total_seconds() // 60)) % (24 * 60)
    return total // 60, total % 60


async def _already_sent(db, key: str) -> bool:
    res = await db.execute(select(SentNotification).where(SentNotification.key == key))
    return res.scalar_one_or_none() is not None


async def _mark_sent(db, key: str) -> None:
    db.add(SentNotification(key=key, sent_at=_now()))
    await db.flush()


def _matches_by_matchday(matches: list[Match]) -> dict[int, list[Match]]:
    by_md: dict[int, list[Match]] = {}
    for m in matches:
        by_md.setdefault(m.matchday, []).append(m)
    return by_md


# ── Polls open ───────────────────────────────────────────────────────────────

async def announce_polls_open(db) -> None:
    now = _now()
    matches = (await db.execute(select(Match))).scalars().all()
    for md, ms in _matches_by_matchday(matches).items():
        polls_open = min(m.polls_open_utc for m in ms)
        first_kick = min(m.kickoff_utc for m in ms)
        # Just opened (within the window) and not yet kicked off.
        if not (polls_open <= now < polls_open + ANNOUNCE_WINDOW and now < first_kick):
            continue
        key = f"polls_open:md={md}"
        if await _already_sent(db, key):
            continue
        ordered = sorted(ms, key=lambda m: m.kickoff_utc)
        text = slack.build_polls_open_text(
            _ist_date_label(first_kick),
            [(m.team_a, m.team_b) for m in ordered],
        )
        if await slack.post_to_slack(text):
            await _mark_sent(db, key)


# ── Vote reminders ─────────────────────────────────────────────────────────────

async def send_vote_reminders(db) -> None:
    now = _now()
    matches = (await db.execute(select(Match))).scalars().all()
    all_users = (await db.execute(select(User).order_by(User.display_name))).scalars().all()

    for md, ms in _matches_by_matchday(matches).items():
        first_kick = min(m.kickoff_utc for m in ms)
        reminder_at = first_kick - timedelta(hours=REMINDER_HOURS_BEFORE)
        if not (reminder_at <= now < reminder_at + ANNOUNCE_WINDOW and now < first_kick):
            continue
        key = f"reminder:md={md}"
        if await _already_sent(db, key):
            continue

        md_match_ids = {m.id for m in ms}
        votes = (await db.execute(
            select(Vote).where(Vote.match_id.in_(md_match_ids))
        )).scalars().all()
        votes_by_user: dict[int, int] = {}
        for v in votes:
            votes_by_user[v.user_id] = votes_by_user.get(v.user_id, 0) + 1

        # Anyone who hasn't picked every match of the day still needs to vote.
        missing = [u.display_name for u in all_users if votes_by_user.get(u.id, 0) < len(ms)]

        if missing:
            text = slack.build_reminder_text(_ist_date_label(first_kick), missing, REMINDER_HOURS_BEFORE)
            if await slack.post_to_slack(text):
                await _mark_sent(db, key)
        else:
            # Everyone's in — nothing to nag about, but record it so we stop checking.
            await _mark_sent(db, key)


# ── Match results (called inline from the result-sync job) ──────────────────────

async def announce_match_result(db, match: Match) -> None:
    key = f"result:match={match.id}"
    if await _already_sent(db, key):
        return
    if match.result not in ("team_a", "team_b"):
        return  # draws / unknown — nothing to announce
    text = slack.build_result_text(
        match.team_a, match.team_b, match.result, match.fifa_rank_a, match.fifa_rank_b
    )
    if await slack.post_to_slack(text):
        await _mark_sent(db, key)


# ── Daily leaderboard ───────────────────────────────────────────────────────────

async def _leaderboard_entries(db) -> list[dict]:
    rows = (await db.execute(
        select(
            User.display_name,
            func.coalesce(func.sum(Score.total), 0).label("total"),
        )
        .outerjoin(Score, Score.user_id == User.id)
        .group_by(User.id)
        .order_by(func.coalesce(func.sum(Score.total), 0).desc(), User.display_name)
    )).all()
    return [
        {"rank": idx + 1, "name": r.display_name, "total": int(r.total)}
        for idx, r in enumerate(rows)
    ]


async def post_daily_leaderboard(db) -> None:
    entries = await _leaderboard_entries(db)
    if not entries:
        return
    text = slack.build_leaderboard_text(entries, title="Daily Standings")
    await slack.post_to_slack(text)


# ── Scheduler entry points (sync wrappers run in BackgroundScheduler threads) ────

async def _notifications_tick() -> None:
    async with SessionLocal() as db:
        try:
            await announce_polls_open(db)
            await send_vote_reminders(db)
            await db.commit()
        except Exception:
            logger.exception("Slack notifications tick failed")
            await db.rollback()


async def _daily_leaderboard() -> None:
    async with SessionLocal() as db:
        try:
            await post_daily_leaderboard(db)
        except Exception:
            logger.exception("Slack daily leaderboard failed")


def run_notifications_job() -> None:
    asyncio.run(_notifications_tick())


def run_daily_leaderboard_job() -> None:
    asyncio.run(_daily_leaderboard())
