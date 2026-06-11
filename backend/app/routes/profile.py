from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.auth import require_user
from app.models import Match, Vote, Score, User, PredictionHistoryRow

router = APIRouter()


@router.get("/api/users/{target_username}/history", response_model=list[PredictionHistoryRow])
async def get_user_history(
    target_username: str,
    _username: str = Depends(require_user),  # caller must have a valid signed link
    db: AsyncSession = Depends(get_db),
):
    """
    Returns prediction history for any user.
    Unsettled match predictions are hidden until the match is settled
    (so you can't peek at someone's vote before kickoff).
    """
    target_result = await db.execute(select(User).where(User.username == target_username))
    target = target_result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")

    matches_result = await db.execute(select(Match).order_by(Match.kickoff_utc))
    all_matches = matches_result.scalars().all()

    votes_result = await db.execute(select(Vote).where(Vote.user_id == target.id))
    vote_map = {v.match_id: v.prediction for v in votes_result.scalars().all()}

    scores_result = await db.execute(select(Score).where(Score.user_id == target.id))
    score_map = {s.match_id: s.total for s in scores_result.scalars().all()}

    rows = []
    for m in all_matches:
        prediction = vote_map.get(m.id)
        correct = None
        if m.result and prediction:
            # A draw is neutral — neither right nor wrong (shows as "—").
            correct = None if m.result == "draw" else (prediction == m.result)

        rows.append(PredictionHistoryRow(
            match_id=m.id,
            match_label=m.match_label,
            kickoff_utc=m.kickoff_utc,
            stage=m.stage,
            # Hide prediction until match is settled (no peeking before kickoff)
            prediction=prediction if m.result is not None else None,
            result=m.result,
            correct=correct,
            points=score_map.get(m.id, 0),
        ))

    return rows
