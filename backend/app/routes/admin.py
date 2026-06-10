import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Match, Vote, Score, User, SettleRequest
from app.scoring import compute_all_scores, MatchData, VoteData

router = APIRouter()

ADMIN_KEY = os.getenv("ADMIN_KEY", "")


def require_admin(x_admin_key: str = Header(...)):
    if not ADMIN_KEY or x_admin_key != ADMIN_KEY:
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
    await db.execute(
        __import__("sqlalchemy", fromlist=["update"]).update(Match).values(result=None)
    )
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
    from app.slack import post_to_slack, slack_enabled
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
