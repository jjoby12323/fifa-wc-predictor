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

    matchday_counter: dict[str, int] = {}

    async with SessionLocal() as db:
        for m in matches_raw:
            stage_raw = m.get("stage", "GROUP_STAGE")
            stage = STAGE_MAP.get(stage_raw, "group")

            # Assign a sequential matchday integer per stage group
            group = m.get("group") or stage_raw
            if group not in matchday_counter:
                matchday_counter[group] = len(matchday_counter) + 1
            matchday = matchday_counter[group]

            home = m["homeTeam"]["name"]
            away = m["awayTeam"]["name"]
            match_label = f"{home} vs {away}"

            kickoff_str = m.get("utcDate", "")
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00")).replace(tzinfo=None)
            polls_open = kickoff - timedelta(hours=24)

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
