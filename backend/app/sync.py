"""
Background scheduler: every 10 minutes, poll football-data.org for results
of matches that kicked off >2 hours ago and auto-settle them.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select, delete

from app.db import SessionLocal
from app.models import Match, Vote, Score, User
from app.scoring import compute_all_scores, MatchData, VoteData
from app import slack, notifications
from app.notifications import announce_match_result

logger = logging.getLogger(__name__)

FOOTBALLDATA_API_KEY = os.getenv("FOOTBALLDATA_API_KEY", "")
FD_BASE = "https://api.football-data.org/v4"

_scheduler = BackgroundScheduler()

# Maps football-data.org fullTime winner values to our internal result keys
_WINNER_MAP = {
    "HOME_TEAM": "team_a",
    "AWAY_TEAM": "team_b",
}


def _sync_results_job():
    asyncio.run(_async_sync_results())


async def _async_sync_results():
    if not FOOTBALLDATA_API_KEY:
        return

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)

    async with SessionLocal() as db:
        unsettled = await db.execute(
            select(Match).where(
                Match.result.is_(None),
                Match.kickoff_utc <= cutoff,
            )
        )
        pending = unsettled.scalars().all()
        if not pending:
            return

        headers = {"X-Auth-Token": FOOTBALLDATA_API_KEY}
        async with httpx.AsyncClient(headers=headers, timeout=10) as client:
            for match in pending:
                if not match.external_id:
                    continue
                try:
                    resp = await client.get(f"{FD_BASE}/matches/{match.external_id}")
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    logger.warning("Failed to fetch result for match %s: %s", match.id, exc)
                    continue

                status = data.get("status")
                if status != "FINISHED":
                    continue

                winner_raw = (data.get("score") or {}).get("winner")
                if winner_raw == "DRAW":
                    result = "draw"   # nobody scores; handled in scoring.py
                else:
                    result = _WINNER_MAP.get(winner_raw)
                if result is None:
                    continue

                match.result = result
                await db.flush()
                await _recompute_scores(db)
                await announce_match_result(db, match)  # Slack post (idempotent, no-op if disabled)

        await db.commit()


async def _recompute_scores(db):
    all_users_result = await db.execute(select(User))
    all_users = all_users_result.scalars().all()

    all_matches_result = await db.execute(select(Match).where(Match.result.isnot(None)))
    settled_matches = {
        m.id: MatchData(
            id=m.id,
            stage=m.stage,
            matchday=m.matchday,
            fifa_rank_a=m.fifa_rank_a,
            fifa_rank_b=m.fifa_rank_b,
            result=m.result,
            kickoff_utc=m.kickoff_utc,
        )
        for m in all_matches_result.scalars().all()
    }

    for user in all_users:
        votes_result = await db.execute(select(Vote).where(Vote.user_id == user.id))
        votes = [
            VoteData(match_id=v.match_id, prediction=v.prediction)
            for v in votes_result.scalars().all()
        ]
        breakdowns = compute_all_scores(votes, settled_matches)
        await db.execute(delete(Score).where(Score.user_id == user.id))
        for match_id, bd in breakdowns.items():
            db.add(Score(
                user_id=user.id,
                match_id=match_id,
                base_points=bd.base_points,
                streak_bonus=bd.streak_bonus,
                upset_bonus=bd.upset_bonus,
                perfect_round_bonus=bd.perfect_round_bonus,
                total=bd.total,
            ))


def start_result_scheduler():
    have_football = bool(FOOTBALLDATA_API_KEY)
    have_slack = slack.slack_enabled()

    if not have_football and not have_slack:
        logger.info("Neither FOOTBALLDATA_API_KEY nor SLACK_WEBHOOK_URL set — scheduler disabled.")
        return

    if have_football:
        _scheduler.add_job(_sync_results_job, "interval", minutes=10, id="sync_results")
        logger.info("Result sync enabled (every 10 minutes).")
    else:
        logger.info("FOOTBALLDATA_API_KEY not set — auto-settle disabled. Use POST /admin/settle manually.")

    if have_slack:
        _scheduler.add_job(notifications.run_notifications_job, "interval", minutes=5, id="slack_notifications")
        hh, mm = notifications.leaderboard_cron_utc()
        _scheduler.add_job(notifications.run_daily_leaderboard_job, "cron", hour=hh, minute=mm, id="slack_leaderboard")
        logger.info("Slack notifications enabled (reminders every 5 min; daily leaderboard at %02d:%02d UTC).", hh, mm)

    _scheduler.start()


def stop_result_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
