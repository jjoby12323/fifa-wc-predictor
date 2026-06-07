from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.auth import require_user
from app.models import Match, Vote, User, MatchStatus, ScoreRow, Score, MatchDetail, MatchVoteEntry
from fastapi import HTTPException

router = APIRouter()

@router.get("/api/whoami")
async def whoami(
    username: str = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    user_result = await db.execute(select(User).where(User.username == username))
    user = user_result.scalar_one_or_none()
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found.")
    return {"username": user.username, "display_name": user.display_name}


def _match_status(match: Match, now: datetime) -> str:
    if match.result is not None:
        return "settled"
    if now >= match.kickoff_utc:
        return "closed"
    if now >= match.polls_open_utc:
        return "open"
    return "pending"


@router.get("/api/matches", response_model=list[MatchStatus])
async def get_matches(
    username: str = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    user_result = await db.execute(select(User).where(User.username == username))
    user = user_result.scalar_one_or_none()
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found. Contact the admin.")

    matches_result = await db.execute(select(Match).order_by(Match.kickoff_utc))
    matches = matches_result.scalars().all()

    votes_result = await db.execute(select(Vote).where(Vote.user_id == user.id))
    vote_map = {v.match_id: v.prediction for v in votes_result.scalars().all()}

    scores_result = await db.execute(select(Score).where(Score.user_id == user.id))
    score_map = {s.match_id: s for s in scores_result.scalars().all()}

    out = []
    for m in matches:
        status = _match_status(m, now)
        my_vote = vote_map.get(m.id)
        correct = None
        if status == "settled" and my_vote is not None:
            correct = my_vote == m.result

        # Underdog = team with higher (worse) FIFA rank number
        if m.fifa_rank_a != m.fifa_rank_b:
            underdog = "team_a" if m.fifa_rank_a > m.fifa_rank_b else "team_b"
        else:
            underdog = None

        out.append(MatchStatus(
            id=m.id,
            match_label=m.match_label,
            team_a=m.team_a,
            team_b=m.team_b,
            kickoff_utc=m.kickoff_utc,
            polls_open_utc=m.polls_open_utc,
            stage=m.stage,
            matchday=m.matchday,
            status=status,
            result=m.result,
            my_vote=my_vote,
            correct=correct,
            underdog=underdog,
        ))
    return out


@router.get("/api/me", response_model=list[ScoreRow])
async def get_me(
    username: str = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    user_result = await db.execute(select(User).where(User.username == username))
    user = user_result.scalar_one_or_none()
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found.")

    scores_result = await db.execute(
        select(Score, Match)
        .join(Match, Score.match_id == Match.id)
        .where(Score.user_id == user.id)
        .order_by(Match.kickoff_utc)
    )
    rows = scores_result.all()

    return [
        ScoreRow(
            match_id=score.id,
            match_label=match.match_label,
            base_points=score.base_points,
            streak_bonus=score.streak_bonus,
            upset_bonus=score.upset_bonus,
            perfect_round_bonus=score.perfect_round_bonus,
            total=score.total,
        )
        for score, match in rows
    ]


@router.get("/api/matches/{match_id}", response_model=MatchDetail)
async def get_match_detail(
    match_id: int,
    username: str = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    # Calling user
    user_result = await db.execute(select(User).where(User.username == username))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    # Match
    match_result = await db.execute(select(Match).where(Match.id == match_id))
    match = match_result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    status = _match_status(match, now)

    underdog = None
    if match.fifa_rank_a != match.fifa_rank_b:
        underdog = "team_a" if match.fifa_rank_a > match.fifa_rank_b else "team_b"

    # All users and their votes for this match
    all_users_result = await db.execute(select(User).order_by(User.display_name))
    all_users = all_users_result.scalars().all()

    votes_result = await db.execute(select(Vote).where(Vote.match_id == match_id))
    vote_map = {v.user_id: v.prediction for v in votes_result.scalars().all()}

    my_vote = vote_map.get(user.id)

    # Hide other participants' picks until the match has kicked off
    # (so people can't peek and change their vote based on what others picked)
    reveal_votes = status in ("closed", "settled")

    vote_entries = [
        MatchVoteEntry(
            display_name=u.display_name,
            prediction=vote_map.get(u.id) if (reveal_votes or u.id == user.id) else (
                "hidden" if vote_map.get(u.id) else None
            ),
        )
        for u in all_users
    ]

    return MatchDetail(
        id=match.id,
        match_label=match.match_label,
        team_a=match.team_a,
        team_b=match.team_b,
        kickoff_utc=match.kickoff_utc,
        stage=match.stage,
        matchday=match.matchday,
        status=status,
        result=match.result,
        underdog=underdog,
        fifa_rank_a=match.fifa_rank_a,
        fifa_rank_b=match.fifa_rank_b,
        my_vote=my_vote,
        votes=vote_entries,
    )
