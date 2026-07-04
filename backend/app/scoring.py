"""
All scoring logic. Pure functions — no DB access. Called from routes/admin.py.
"""
from typing import NamedTuple

# Group games are worth 1; every knockout round is a flat 2 (no escalation).
STAGE_MULTIPLIER = {
    "group": 1,
    "r32": 2,
    "r16": 2,
    "qf": 2,
    "sf": 2,
    "final": 2,
    "third": 2,
}


class MatchData(NamedTuple):
    id: int
    stage: str
    matchday: int
    fifa_rank_a: int
    fifa_rank_b: int
    result: str  # "team_a", "team_b", or "draw"
    kickoff_utc: object


class VoteData(NamedTuple):
    match_id: int
    prediction: str


class ScoreBreakdown(NamedTuple):
    base_points: float   # a draw pays a 0.5 consolation to voters; wins are whole points
    streak_bonus: int
    perfect_round_bonus: int
    participation_bonus: int

    @property
    def total(self) -> float:
        return self.base_points + self.streak_bonus + self.perfect_round_bonus + self.participation_bonus


def compute_base_points(prediction: str, match: MatchData) -> float:
    if match.result == "draw":
        return 0.5  # consolation — the match couldn't be called (there's no draw to pick)
    if prediction == match.result:
        return STAGE_MULTIPLIER.get(match.stage, 1)
    return 0


def compute_streak_bonus_per_match(votes: list[VoteData], matches: dict[int, MatchData]) -> dict[int, int]:
    """
    Returns {match_id: streak_bonus} for all votes, ordered chronologically.
    +1 is assigned to the match that triggers each multiple-of-3 streak.
    """
    ordered = sorted(
        [(v, matches[v.match_id]) for v in votes if v.match_id in matches],
        key=lambda x: x[1].kickoff_utc,
    )
    streak = 0
    bonuses: dict[int, int] = {v.match_id: 0 for v in votes}
    for vote, match in ordered:
        if match.result == "draw":
            continue  # a draw is neutral — it neither extends nor breaks a streak
        if vote.prediction == match.result:
            streak += 1
            if streak % 3 == 0:
                bonuses[vote.match_id] = bonuses.get(vote.match_id, 0) + 1
        else:
            streak = 0
    return bonuses


def compute_participation_bonus_per_match(votes: list[VoteData], matches: dict[int, MatchData]) -> dict[int, int]:
    """
    Returns {match_id: participation_bonus}. +1 for every 3 matches a user has
    voted on (settled only), regardless of whether the pick was correct — awarded
    on the match that completes each group of 3, chronologically.
    """
    ordered = sorted(
        [(v, matches[v.match_id]) for v in votes if v.match_id in matches],
        key=lambda x: x[1].kickoff_utc,
    )
    bonuses: dict[int, int] = {v.match_id: 0 for v in votes}
    count = 0
    for vote, _match in ordered:
        count += 1
        if count % 3 == 0:
            bonuses[vote.match_id] = bonuses.get(vote.match_id, 0) + 1
    return bonuses


def compute_perfect_round_bonus(
    votes_by_matchday: dict[int, list[VoteData]],
    matches_by_matchday: dict[int, list[MatchData]],
) -> dict[int, int]:
    """
    Returns {match_id: perfect_round_bonus}.
    +2 awarded on the last match of the matchday if the voter played the whole day
    and correctly called every decisive (non-draw) match. Draws are free squares —
    they don't need to be called and don't block the sweep. Only evaluated once all
    matches in the matchday are settled. Single-match days (e.g. the Final) don't
    qualify, and an all-draw day has nothing to sweep.
    """
    bonuses: dict[int, int] = {}
    for matchday, day_matches in matches_by_matchday.items():
        if len(day_matches) <= 1:
            continue  # a single-match day isn't a sweep — no perfect bonus
        if any(m.result is None for m in day_matches):
            continue
        decisive = [m for m in day_matches if m.result != "draw"]
        if not decisive:
            continue  # an all-draw day has nothing to sweep
        day_votes = votes_by_matchday.get(matchday, [])
        if len(day_votes) != len(day_matches):
            continue  # must have played the whole day
        vote_map = {v.match_id: v.prediction for v in day_votes}
        if all(vote_map.get(m.id) == m.result for m in decisive):
            last_match = max(day_matches, key=lambda m: m.kickoff_utc)
            bonuses[last_match.id] = bonuses.get(last_match.id, 0) + 2
    return bonuses


def compute_all_scores(
    votes: list[VoteData],
    all_settled_matches: dict[int, MatchData],
) -> dict[int, ScoreBreakdown]:
    """
    Compute full score breakdown for every vote a user has cast (against settled matches only).
    Returns {match_id: ScoreBreakdown}.
    """
    settled_votes = [v for v in votes if v.match_id in all_settled_matches]

    streak_bonuses = compute_streak_bonus_per_match(settled_votes, all_settled_matches)
    participation_bonuses = compute_participation_bonus_per_match(settled_votes, all_settled_matches)

    votes_by_matchday: dict[int, list[VoteData]] = {}
    matches_by_matchday: dict[int, list[MatchData]] = {}
    for v in settled_votes:
        m = all_settled_matches[v.match_id]
        votes_by_matchday.setdefault(m.matchday, []).append(v)
        matches_by_matchday.setdefault(m.matchday, []).append(m)

    perfect_bonuses = compute_perfect_round_bonus(votes_by_matchday, matches_by_matchday)

    result: dict[int, ScoreBreakdown] = {}
    for v in settled_votes:
        m = all_settled_matches[v.match_id]
        result[v.match_id] = ScoreBreakdown(
            base_points=compute_base_points(v.prediction, m),
            streak_bonus=streak_bonuses.get(v.match_id, 0),
            perfect_round_bonus=perfect_bonuses.get(v.match_id, 0),
            participation_bonus=participation_bonuses.get(v.match_id, 0),
        )
    return result
