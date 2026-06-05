from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.auth import require_user
from app.models import Match, Vote, User, VoteRequest

router = APIRouter()


@router.post("/api/vote")
async def submit_vote(
    body: VoteRequest,
    username: str = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if body.prediction not in ("team_a", "team_b"):
        raise HTTPException(status_code=400, detail="prediction must be 'team_a' or 'team_b'")

    user_result = await db.execute(select(User).where(User.username == username))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found. Contact the admin.")

    match_result = await db.execute(select(Match).where(Match.id == body.match_id))
    match = match_result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if now < match.polls_open_utc:
        raise HTTPException(status_code=400, detail="Voting hasn't opened for this match yet.")
    if now >= match.kickoff_utc:
        raise HTTPException(status_code=400, detail="This match has already kicked off — voting is closed.")

    existing = await db.execute(
        select(Vote).where(Vote.user_id == user.id, Vote.match_id == match.id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="You've already voted for this match.")

    vote = Vote(
        user_id=user.id,
        match_id=match.id,
        prediction=body.prediction,
        submitted_at=now,
    )
    db.add(vote)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="You've already voted for this match.")

    return {"status": "ok", "match_id": match.id, "prediction": body.prediction}
