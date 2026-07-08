from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.auth import require_user
from app.models import Match, Vote, User, MatchStatus, Score, MatchDetail, MatchVoteEntry

router = APIRouter()

@router.get("/api/whoami")
async def whoami(
    username: str = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    user_result = await db.execute(select(User).where(User.username == username))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"username": user.username, "display_name": user.display_name}


def _match_status(match: Match, now: datetime) -> str:
    if match.result is not None:
        return "settled"
    if now >= match.kickoff_utc:
        return "closed"
    # Group matches use the fixed 48h polls-open window. Knockout rounds instead unlock the
    # moment their teams are known (i.e. the previous round has concluded), so a whole round
    # becomes votable together — well ahead of kickoff.
    if match.stage == "group":
        return "open" if now >= match.polls_open_utc else "pending"
    teams_known = match.team_a != "TBD" and match.team_b != "TBD"
    return "open" if teams_known else "pending"


@router.get("/api/matches", response_model=list[MatchStatus])
async def get_matches(
    username: str = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    user_result = await db.execute(select(User).where(User.username == username))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found. Contact the admin.")

    # Only votable matches — knockout fixtures with undecided teams ("TBD") are
    # excluded here (they live on the bracket page until teams are confirmed).
    matches_result = await db.execute(
        select(Match)
        .where(Match.team_a != "TBD", Match.team_b != "TBD")
        .order_by(Match.kickoff_utc)
    )
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
            # A draw is neutral — nobody could call it, so it's neither right nor wrong.
            correct = None if m.result == "draw" else (my_vote == m.result)

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
            score_a=m.score_a,
            score_b=m.score_b,
            pens_a=m.pens_a,
            pens_b=m.pens_b,
            my_vote=my_vote,
            correct=correct,
        ))
    return out


@router.get("/api/matches/{match_id}", response_model=MatchDetail)
async def get_match_detail(
    match_id: int,
    username: str = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    user_result = await db.execute(select(User).where(User.username == username))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    match_result = await db.execute(select(Match).where(Match.id == match_id))
    match = match_result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    status = _match_status(match, now)

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
        polls_open_utc=match.polls_open_utc,
        stage=match.stage,
        matchday=match.matchday,
        status=status,
        result=match.result,
        score_a=match.score_a,
        score_b=match.score_b,
        pens_a=match.pens_a,
        pens_b=match.pens_b,
        fifa_rank_a=match.fifa_rank_a,
        fifa_rank_b=match.fifa_rank_b,
        my_vote=my_vote,
        votes=vote_entries,
    )
