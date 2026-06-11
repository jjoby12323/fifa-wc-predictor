import os
import hmac
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Match, Vote, Score, User, Message, SettleRequest
from app.scoring import compute_all_scores, MatchData, VoteData
from app.slack import post_to_slack, slack_enabled

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
    if body.result not in ("team_a", "team_b"):
        raise HTTPException(status_code=400, detail="result must be 'team_a' or 'team_b'")

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


@router.post("/admin/slack-test")
async def slack_test(_=Depends(require_admin)):
    """Fire a test message to verify SLACK_WEBHOOK_URL is wired up correctly."""
    if not slack_enabled():
        raise HTTPException(status_code=400, detail="SLACK_WEBHOOK_URL not set.")
    ok = await post_to_slack(":wave: Test from the FIFA WC 2026 Predictor bot — webhook is live!")
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
        if now < polls_open:
            status = "upcoming"
        elif now < first_kickoff:
            status = "open"
        else:
            status = "closed"
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
