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
            if set_results and m.get("status") == "FINISHED":
                winner = (m.get("score") or {}).get("winner")
                if winner == "HOME_TEAM":
                    result = "team_a"
                elif winner == "AWAY_TEAM":
                    result = "team_b"

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
                ))
        await db.commit()

    return len(parsed)
