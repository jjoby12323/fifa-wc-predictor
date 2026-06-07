"""
All scoring logic. Pure functions — no DB access. Called from routes/admin.py.
"""
from typing import NamedTuple

STAGE_MULTIPLIER = {
    "group": 1,
    "r32": 2,   # WC2026 Round of 32 (new in 48-team format)
    "r16": 3,
    "qf": 4,
    "sf": 5,
    "final": 6,
}


class MatchData(NamedTuple):
    id: int
    stage: str
    matchday: int
    fifa_rank_a: int
    fifa_rank_b: int
    result: str  # "team_a" or "team_b"
    kickoff_utc: object


class VoteData(NamedTuple):
    match_id: int
    prediction: str


class ScoreBreakdown(NamedTuple):
    base_points: int
    upset_bonus: int
    streak_bonus: int
    perfect_round_bonus: int

    @property
    def total(self) -> int:
        return self.base_points + self.upset_bonus + self.streak_bonus + self.perfect_round_bonus


def compute_base_points(prediction: str, match: MatchData) -> int:
    if prediction == match.result:
        return STAGE_MULTIPLIER.get(match.stage, 1)
    return 0


def compute_upset_bonus(prediction: str, match: MatchData) -> int:
    if prediction != match.result:
        return 0
    if match.result == "team_a" and match.fifa_rank_a > match.fifa_rank_b:
        return 1
    if match.result == "team_b" and match.fifa_rank_b > match.fifa_rank_a:
        return 1
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
        if vote.prediction == match.result:
            streak += 1
            if streak % 3 == 0:
                bonuses[vote.match_id] = bonuses.get(vote.match_id, 0) + 1
        else:
            streak = 0
    return bonuses


def compute_perfect_round_bonus(
    votes_by_matchday: dict[int, list[VoteData]],
    matches_by_matchday: dict[int, list[MatchData]],
) -> dict[int, int]:
    """
    Returns {match_id: perfect_round_bonus}.
    +2 awarded on the last match of the matchday if all predictions were correct.
    Only evaluated once all matches in the matchday are settled.
    """
    bonuses: dict[int, int] = {}
    for matchday, day_matches in matches_by_matchday.items():
        if any(m.result is None for m in day_matches):
            continue
        day_votes = votes_by_matchday.get(matchday, [])
        vote_map = {v.match_id: v.prediction for v in day_votes}
        all_correct = all(
            vote_map.get(m.id) == m.result for m in day_matches
        )
        if all_correct and len(day_votes) == len(day_matches):
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
            upset_bonus=compute_upset_bonus(v.prediction, m),
            streak_bonus=streak_bonuses.get(v.match_id, 0),
            perfect_round_bonus=perfect_bonuses.get(v.match_id, 0),
        )
    return result
