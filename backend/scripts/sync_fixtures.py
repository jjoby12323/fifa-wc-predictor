"""
Fetch all FIFA World Cup 2026 fixtures from football-data.org and upsert into the DB.
Run once before the tournament, or re-run if fixtures change.

Usage:
    cd backend
    python -m scripts.sync_fixtures
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db import engine, SessionLocal, Base
from app.models import Match

FOOTBALLDATA_API_KEY = os.getenv("FOOTBALLDATA_API_KEY", "")
FD_BASE = "https://api.football-data.org/v4"

RANKINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "rankings.json")

# A "matchday" = all matches kicking off on the same calendar date in IST.
# Voting for a whole matchday opens VOTING_WINDOW before its first kickoff.
IST_OFFSET = timedelta(hours=5, minutes=30)
VOTING_WINDOW = timedelta(hours=48)


def _ist_date(kickoff_utc: datetime):
    """Calendar date a kickoff falls on in IST (UTC+5:30)."""
    return (kickoff_utc + IST_OFFSET).date()

STAGE_MAP = {
    "GROUP_STAGE": "group",
    "ROUND_OF_16": "r16",
    "QUARTER_FINALS": "qf",
    "SEMI_FINALS": "sf",
    "FINAL": "final",
    "THIRD_PLACE": "sf",
}


def load_rankings() -> dict[str, int]:
    if os.path.exists(RANKINGS_PATH):
        with open(RANKINGS_PATH) as f:
            return json.load(f)
    print("Warning: data/rankings.json not found — all FIFA ranks defaulting to 50.")
    return {}


async def sync():
    if not FOOTBALLDATA_API_KEY:
        print("Error: FOOTBALLDATA_API_KEY not set in .env")
        sys.exit(1)

    rankings = load_rankings()

    async with httpx.AsyncClient(
        headers={"X-Auth-Token": FOOTBALLDATA_API_KEY}, timeout=20
    ) as client:
        print("Fetching WC 2026 fixtures from football-data.org...")
        resp = await client.get(f"{FD_BASE}/competitions/WC/matches")
        resp.raise_for_status()
        data = resp.json()

    matches_raw = data.get("matches", [])
    print(f"  {len(matches_raw)} matches found.")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # ── First pass: parse + keep only matches with confirmed teams ──────────────
    parsed = []
    for m in matches_raw:
        # Skip matches where teams aren't confirmed yet (knockout placeholders)
        home = (m.get("homeTeam") or {}).get("name")
        away = (m.get("awayTeam") or {}).get("name")
        if not home or not away:
            continue
        kickoff = datetime.fromisoformat(
            m.get("utcDate", "").replace("Z", "+00:00")
        ).replace(tzinfo=None)
        parsed.append((m, home, away, kickoff))

    # ── Group into matchdays by IST calendar date, numbered chronologically ─────
    sorted_dates = sorted({_ist_date(k) for (_, _, _, k) in parsed})
    matchday_of = {d: i + 1 for i, d in enumerate(sorted_dates)}

    # Voting opens VOTING_WINDOW before each matchday's first kickoff — the same
    # open time applies to every match in that matchday.
    first_kickoff: dict[int, datetime] = {}
    for (_, _, _, k) in parsed:
        md = matchday_of[_ist_date(k)]
        if md not in first_kickoff or k < first_kickoff[md]:
            first_kickoff[md] = k
    polls_open_of = {md: k - VOTING_WINDOW for md, k in first_kickoff.items()}

    # ── Second pass: upsert ─────────────────────────────────────────────────────
    async with SessionLocal() as db:
        for (m, home, away, kickoff) in parsed:
            stage = STAGE_MAP.get(m.get("stage", "GROUP_STAGE"), "group")
            matchday = matchday_of[_ist_date(kickoff)]
            polls_open = polls_open_of[matchday]
            match_label = f"{home} vs {away}"

            result = None
            if m.get("status") == "FINISHED":
                winner = (m.get("score") or {}).get("winner")
                if winner == "HOME_TEAM":
                    result = "team_a"
                elif winner == "AWAY_TEAM":
                    result = "team_b"

            existing = await db.execute(
                select(Match).where(Match.external_id == m["id"])
            )
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
    print("Done. Fixtures synced.")


if __name__ == "__main__":
    asyncio.run(sync())
