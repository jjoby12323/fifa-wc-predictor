from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User, Score, LeaderboardEntry

router = APIRouter()


@router.get("/api/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    db: AsyncSession = Depends(get_db),
):
    # Public — the leaderboard is shared data (it's what the Slack bot posts to
    # everyone), so the link in those posts works without a signed personal URL.
    # Per-player detail (/api/me, history) stays auth-gated.
    rows = await db.execute(
        select(
            User.username,
            User.display_name,
            func.coalesce(func.sum(Score.total), 0).label("total"),
            func.coalesce(func.sum(Score.base_points), 0).label("base"),
            func.coalesce(func.sum(Score.streak_bonus), 0).label("streak"),
            func.coalesce(func.sum(Score.perfect_round_bonus), 0).label("perfect"),
            func.coalesce(func.sum(Score.participation_bonus), 0).label("participation"),
        )
        .outerjoin(Score, Score.user_id == User.id)
        .group_by(User.id)
        .order_by(func.coalesce(func.sum(Score.total), 0).desc())
    )
    entries = rows.all()

    return [
        LeaderboardEntry(
            rank=idx + 1,
            username=row.username,
            display_name=row.display_name,
            total=row.total,
            base=row.base,
            streak=row.streak,
            perfect=row.perfect,
            participation=row.participation,
        )
        for idx, row in enumerate(entries)
    ]
