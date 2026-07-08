import os
import hmac
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from app.db import get_db
from app.models import Match, Vote, Score, User, Message, SettleRequest, AnnounceRequest
from app.scoring import compute_all_scores, MatchData, VoteData
from app.slack import post_to_slack, slack_enabled
from app.fixtures import FD_BASE, parse_fulltime_score, parse_penalty_score, resolve_result
from app.sync import _recompute_scores
from app.routes.matches import _match_status

IST_OFFSET = timedelta(hours=5, minutes=30)

router = APIRouter()

ADMIN_KEY = os.getenv("ADMIN_KEY", "")


def require_admin(x_admin_key: str = Header(...)):
    if not ADMIN_KEY or not hmac.compare_digest(x_admin_key, ADMIN_KEY):
        raise HTTPException(status_code=403, detail="Invalid admin key.")


@router.post("/admin/settle")
async def settle_match(
    body: SettleRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    if body.result not in ("team_a", "team_b", "draw"):
        raise HTTPException(status_code=400, detail="result must be 'team_a', 'team_b', or 'draw'")

    match_result = await db.execute(select(Match).where(Match.id == body.match_id))
    match = match_result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    match.result = body.result
    await db.flush()

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
                perfect_round_bonus=bd.perfect_round_bonus,
                participation_bonus=bd.participation_bonus,
                total=bd.total,
            ))

    await db.commit()
    return {"status": "settled", "match_id": body.match_id, "result": body.result}


@router.post("/admin/reset-scores")
async def reset_scores(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Wipe all votes, scores, and match results. Keeps users and fixtures."""
    await db.execute(delete(Score))
    await db.execute(delete(Vote))
    await db.execute(update(Match).values(result=None))
    await db.commit()
    return {"status": "reset", "cleared": ["votes", "scores", "match results"]}


@router.post("/admin/reset-all")
async def reset_all(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Nuclear reset — wipes everything including users and fixtures. Re-run seed after this."""
    await db.execute(delete(Score))
    await db.execute(delete(Vote))
    await db.execute(delete(Match))
    await db.execute(delete(User))
    await db.commit()
    return {"status": "reset", "cleared": ["votes", "scores", "matches", "users"]}


@router.post("/admin/backfill-scores")
async def backfill_scores(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """One-time: fill final scores for matches that settled before score capture existed.

    Re-fetches the WC fixtures once and writes score_a/score_b where they're missing on an
    already-settled match. Touches only the score columns — never the result, the points,
    or Slack. Safe to run repeatedly (skips matches that already have a score).
    """
    api_key = os.getenv("FOOTBALLDATA_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="FOOTBALLDATA_API_KEY not set.")

    async with httpx.AsyncClient(headers={"X-Auth-Token": api_key}, timeout=20) as client:
        resp = await client.get(f"{FD_BASE}/competitions/WC/matches")
        resp.raise_for_status()
        api_matches = resp.json().get("matches", [])

    score_by_ext: dict[int, tuple[int, int]] = {}
    for am in api_matches:
        if am.get("status") == "FINISHED":
            sa, sb = parse_fulltime_score(am)
            if sa is not None and sb is not None:
                score_by_ext[am["id"]] = (sa, sb)

    ours = (await db.execute(
        select(Match).where(Match.result.isnot(None), Match.external_id.isnot(None))
    )).scalars().all()

    updated = []
    for m in ours:
        if m.score_a is not None and m.score_b is not None:
            continue  # already has a score — leave it
        sc = score_by_ext.get(m.external_id)
        if sc:
            m.score_a, m.score_b = sc
            updated.append(f"{m.match_label} {sc[0]}-{sc[1]}")
    await db.commit()
    return {"status": "ok", "settled": len(ours), "filled": len(updated), "matches": updated}


@router.post("/admin/resync-results")
async def resync_results(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Re-derive result + score from football-data for every FINISHED match and correct any
    that differ, then recompute all scores. Heals a shootout that football-data first reported
    as a draw, or one left unsettled because `winner` was null. Safe to run repeatedly.
    """
    api_key = os.getenv("FOOTBALLDATA_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="FOOTBALLDATA_API_KEY not set.")

    # The feed can report a shootout as "level" (no decisive penalties/fullTime) on some
    # polls, so re-fetch a few times and keep the first decisive snapshot per match.
    by_ext: dict[int, tuple] = {}
    async with httpx.AsyncClient(headers={"X-Auth-Token": api_key}, timeout=20) as client:
        for _attempt in range(3):
            resp = await client.get(f"{FD_BASE}/competitions/WC/matches")
            resp.raise_for_status()
            for am in resp.json().get("matches", []):
                if am["id"] in by_ext or am.get("status") != "FINISHED":
                    continue
                r = resolve_result(am)
                if r:
                    sa, sb = parse_fulltime_score(am)
                    pa, pb = parse_penalty_score(am)
                    by_ext[am["id"]] = (r, sa, sb, pa, pb)

    ours = (await db.execute(select(Match).where(Match.external_id.isnot(None)))).scalars().all()
    changed = []
    for m in ours:
        info = by_ext.get(m.external_id)
        if not info:
            continue
        r, sa, sb, pa, pb = info
        if (m.result, m.score_a, m.score_b, m.pens_a, m.pens_b) != (r, sa, sb, pa, pb):
            changed.append(f"{m.match_label}: {m.result}→{r} ({sa}-{sb})")
            m.result, m.score_a, m.score_b, m.pens_a, m.pens_b = r, sa, sb, pa, pb
    if changed:
        await db.flush()
        await _recompute_scores(db)
    await db.commit()
    return {"status": "ok", "corrected": len(changed), "matches": changed}


@router.post("/admin/slack-test")
async def slack_test(_=Depends(require_admin)):
    """Fire a test message to verify SLACK_WEBHOOK_URL is wired up correctly."""
    if not slack_enabled():
        raise HTTPException(status_code=400, detail="SLACK_WEBHOOK_URL not set.")
    ok = await post_to_slack(":wave: Test from the FIFA WC 2026 Predictor bot — webhook is live!")
    return {"status": "ok" if ok else "failed"}


@router.post("/admin/announce")
async def announce(body: AnnounceRequest, _=Depends(require_admin)):
    """Post a free-form message to the Slack channel as the bot."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message text is required.")
    if len(text) > 4000:
        raise HTTPException(status_code=400, detail="Message too long (4000 character max).")
    if not slack_enabled():
        raise HTTPException(status_code=400, detail="SLACK_WEBHOOK_URL not set.")
    ok = await post_to_slack(text)
    return {"status": "ok" if ok else "failed"}


@router.get("/admin/matches")
async def list_matches(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    result = await db.execute(select(Match).order_by(Match.kickoff_utc))
    matches = result.scalars().all()
    return [
        {
            "id": m.id,
            "label": m.match_label,
            "team_a": m.team_a,
            "team_b": m.team_b,
            "kickoff_utc": m.kickoff_utc.isoformat(),
            "stage": m.stage,
            "result": m.result,
        }
        for m in matches
    ]


@router.get("/admin/participation")
async def participation(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Engagement overview — who's voting and chatting. Never exposes individual picks."""
    now = datetime.utcnow()

    users = (await db.execute(select(User))).scalars().all()
    matches = (await db.execute(select(Match).order_by(Match.kickoff_utc))).scalars().all()
    votes = (await db.execute(select(Vote))).scalars().all()
    messages = (await db.execute(select(Message))).scalars().all()

    votes_per_user: dict[int, int] = defaultdict(int)
    msgs_per_user: dict[int, int] = defaultdict(int)
    last_active: dict[int, datetime] = {}
    for v in votes:
        votes_per_user[v.user_id] += 1
        if v.submitted_at and v.submitted_at > last_active.get(v.user_id, datetime.min):
            last_active[v.user_id] = v.submitted_at
    for m in messages:
        msgs_per_user[m.user_id] += 1
        if m.created_at and m.created_at > last_active.get(m.user_id, datetime.min):
            last_active[m.user_id] = m.created_at

    players = [
        {
            "display_name": u.display_name,
            "total_votes": votes_per_user.get(u.id, 0),
            "chat_messages": msgs_per_user.get(u.id, 0),
            "last_active": last_active[u.id].isoformat() + "Z" if u.id in last_active else None,
        }
        for u in users
    ]

    match_matchday = {m.id: m.matchday for m in matches}
    voters_per_matchday: dict[int, set] = defaultdict(set)
    for v in votes:
        md = match_matchday.get(v.match_id)
        if md is not None:
            voters_per_matchday[md].add(v.user_id)

    matches_by_matchday: dict[int, list] = defaultdict(list)
    for m in matches:
        matches_by_matchday[m.matchday].append(m)

    matchdays = []
    for md in sorted(matches_by_matchday):
        day = matches_by_matchday[md]
        first_kickoff = min(m.kickoff_utc for m in day)
        polls_open = min(m.polls_open_utc for m in day)
        # Day status from the real per-match voting rule (knockouts open on teams-known, not
        # the 48h window) — so open knockout rounds show as open here too.
        statuses = [_match_status(m, now) for m in day]
        if any(s == "open" for s in statuses):
            status = "open"
        elif all(s in ("closed", "settled") for s in statuses):
            status = "closed"
        else:
            status = "upcoming"
        voted_ids = voters_per_matchday.get(md, set())
        matchdays.append({
            "matchday": md,
            "date": (first_kickoff + IST_OFFSET).date().isoformat(),
            "status": status,
            "kickoff_utc": first_kickoff.isoformat() + "Z",
            "polls_open_utc": polls_open.isoformat() + "Z",
            "total_matches": len(day),
            "player_count": len(users),
            "voted_count": sum(1 for u in users if u.id in voted_ids),
            "not_voted": [u.display_name for u in users if u.id not in voted_ids],
        })

    return {
        "generated_at": now.isoformat() + "Z",
        "players": players,
        "matchdays": matchdays,
    }
