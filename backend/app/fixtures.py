"""
Pull WC fixtures from football-data.org and upsert them into the DB.

Shared by the manual seed script (scripts/sync_fixtures.py) and the scheduled
fixture sync (app/sync.py), so knockout teams and schedule changes flow in
automatically once teams are decided.

A "matchday" = all matches kicking off on the same calendar date in IST.
Voting for a whole matchday opens VOTING_WINDOW before its first kickoff.
"""
import json
import logging
import os
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select

from app.db import engine, SessionLocal, Base
from app.models import Match

logger = logging.getLogger(__name__)

FOOTBALLDATA_API_KEY = os.getenv("FOOTBALLDATA_API_KEY", "")
FD_BASE = "https://api.football-data.org/v4"
RANKINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "rankings.json")

IST_OFFSET = timedelta(hours=5, minutes=30)
VOTING_WINDOW = timedelta(hours=48)

STAGE_MAP = {
    "GROUP_STAGE": "group",
    "LAST_32": "r32",        # WC2026 48-team format: Round of 32
    "LAST_16": "r16",
    "ROUND_OF_16": "r16",    # legacy naming, kept for safety
    "QUARTER_FINALS": "qf",
    "SEMI_FINALS": "sf",
    "FINAL": "final",
    "THIRD_PLACE": "third",  # own stage so it sits in the bracket centre, not SF
}


def load_rankings() -> dict[str, int]:
    if os.path.exists(RANKINGS_PATH):
        with open(RANKINGS_PATH) as f:
            return json.load(f)
    logger.warning("data/rankings.json not found — FIFA ranks default to 50.")
    return {}


def _ist_date(kickoff_utc: datetime):
    return (kickoff_utc + IST_OFFSET).date()


_WINNER_MAP = {"HOME_TEAM": "team_a", "AWAY_TEAM": "team_b"}


def parse_fulltime_score(match_payload: dict) -> tuple[int | None, int | None]:
    """(home_goals, away_goals) to DISPLAY, or (None, None).

    For a match that went to extra time or a shootout, this is the on-field score
    (regular + extra time) — the level score that sent it to penalties — NOT football-data's
    `fullTime`, which folds the shootout in. For a normal match it's `fullTime`. Keeping the
    score level for a shootout is what makes the UI/Slack read it as "won on penalties".
    """
    sc = match_payload.get("score") or {}
    reg = sc.get("regularTime") or {}
    if reg.get("home") is not None and reg.get("away") is not None:
        ext = sc.get("extraTime") or {}
        return reg["home"] + (ext.get("home") or 0), reg["away"] + (ext.get("away") or 0)
    ft = sc.get("fullTime") or {}
    return ft.get("home"), ft.get("away")


def parse_penalty_score(match_payload: dict) -> tuple[int | None, int | None]:
    """(home_pens, away_pens) for a shootout, else (None, None).

    Prefer football-data's `penalties` when it's decisive; otherwise back it out of
    `fullTime` minus the on-field (regular + extra time) score — this feed encodes
    fullTime = on-field + shootout, and its `penalties` field is often a stub tie.
    """
    sc = match_payload.get("score") or {}
    if sc.get("duration") != "PENALTY_SHOOTOUT":
        return None, None
    pen = sc.get("penalties") or {}
    ph, pa = pen.get("home"), pen.get("away")
    if ph is not None and pa is not None and ph != pa:
        return ph, pa
    ft = sc.get("fullTime") or {}
    oh, oa = parse_fulltime_score(match_payload)
    if ft.get("home") is not None and ft.get("away") is not None and oh is not None and oa is not None:
        dh, da = ft["home"] - oh, ft["away"] - oa
        if dh >= 0 and da >= 0 and dh != da:
            return dh, da
    return None, None


def resolve_result(match_payload: dict) -> str | None:
    """Map a FINISHED football-data match to our result key, or None if undecided.

    football-data leaves `score.winner` null for penalty shootouts (the outcome lives in
    `penalties`/`fullTime`), so derive the winner from those when the field isn't decisive.
    """
    sc = match_payload.get("score") or {}
    winner = sc.get("winner")
    if winner in _WINNER_MAP:
        return _WINNER_MAP[winner]
    if sc.get("duration") == "PENALTY_SHOOTOUT":
        # winner is null/DRAW on a shootout — read it off the shootout (or aggregate) score.
        for seg in (sc.get("penalties"), sc.get("fullTime")):
            seg = seg or {}
            h, a = seg.get("home"), seg.get("away")
            if h is not None and a is not None and h != a:
                return "team_a" if h > a else "team_b"
        return None  # shootout not fully recorded yet — wait for the next poll
    if winner == "DRAW":
        return "draw"
    return None


async def sync_fixtures(set_results: bool = True) -> int:
    """
    Upsert every WC fixture; returns the number processed.

    set_results=True also settles FINISHED matches — used for the manual/initial
    seed. The scheduled job passes set_results=False: it refreshes teams/schedule
    only, leaving result-settling (and the score recompute) to
    sync._sync_results_job so the two never clash.
    """
    if not FOOTBALLDATA_API_KEY:
        logger.info("FOOTBALLDATA_API_KEY not set — skipping fixture sync.")
        return 0

    rankings = load_rankings()
    async with httpx.AsyncClient(headers={"X-Auth-Token": FOOTBALLDATA_API_KEY}, timeout=20) as client:
        resp = await client.get(f"{FD_BASE}/competitions/WC/matches")
        resp.raise_for_status()
        matches_raw = resp.json().get("matches", [])

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Knockout matches have no teams yet, so they're stored as "TBD" (populates the
    # bracket skeleton; kept out of the votable list in routes/matches.py).
    parsed = []
    for m in matches_raw:
        home = (m.get("homeTeam") or {}).get("name") or "TBD"
        away = (m.get("awayTeam") or {}).get("name") or "TBD"
        kickoff = datetime.fromisoformat(
            m.get("utcDate", "").replace("Z", "+00:00")
        ).replace(tzinfo=None)
        parsed.append((m, home, away, kickoff))

    # Group into matchdays by IST date, numbered chronologically.
    sorted_dates = sorted({_ist_date(k) for (_, _, _, k) in parsed})
    matchday_of = {d: i + 1 for i, d in enumerate(sorted_dates)}
    first_kickoff: dict[int, datetime] = {}
    for (_, _, _, k) in parsed:
        md = matchday_of[_ist_date(k)]
        if md not in first_kickoff or k < first_kickoff[md]:
            first_kickoff[md] = k
    polls_open_of = {md: k - VOTING_WINDOW for md, k in first_kickoff.items()}

    async with SessionLocal() as db:
        for (m, home, away, kickoff) in parsed:
            stage = STAGE_MAP.get(m.get("stage", "GROUP_STAGE"), "group")
            matchday = matchday_of[_ist_date(kickoff)]
            polls_open = polls_open_of[matchday]
            match_label = f"{home} vs {away}"

            result = None
            score_a = score_b = pens_a = pens_b = None
            if set_results and m.get("status") == "FINISHED":
                result = resolve_result(m)
                score_a, score_b = parse_fulltime_score(m)
                pens_a, pens_b = parse_penalty_score(m)

            existing = await db.execute(select(Match).where(Match.external_id == m["id"]))
            existing_match = existing.scalar_one_or_none()
            if existing_match:
                existing_match.match_label = match_label
                existing_match.team_a = home
                existing_match.team_b = away
                existing_match.kickoff_utc = kickoff
                existing_match.polls_open_utc = polls_open
                existing_match.stage = stage
                existing_match.matchday = matchday
                existing_match.fifa_rank_a = rankings.get(home, 50)
                existing_match.fifa_rank_b = rankings.get(away, 50)
                if result:
                    existing_match.result = result
                if score_a is not None and score_b is not None:
                    existing_match.score_a = score_a
                    existing_match.score_b = score_b
                if pens_a is not None and pens_b is not None:
                    existing_match.pens_a = pens_a
                    existing_match.pens_b = pens_b
            else:
                db.add(Match(
                    external_id=m["id"],
                    match_label=match_label,
                    team_a=home,
                    team_b=away,
                    kickoff_utc=kickoff,
                    polls_open_utc=polls_open,
                    stage=stage,
                    matchday=matchday,
                    fifa_rank_a=rankings.get(home, 50),
                    fifa_rank_b=rankings.get(away, 50),
                    result=result,
                    score_a=score_a,
                    score_b=score_b,
                    pens_a=pens_a,
                    pens_b=pens_b,
                ))
        await db.commit()

    return len(parsed)
