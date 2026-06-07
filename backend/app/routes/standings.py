"""
/api/standings  — group-stage standings proxied from football-data.org (5-min cache)
/api/bracket    — all knockout matches from the DB
"""
import os
import time
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Match

router = APIRouter()
logger = logging.getLogger(__name__)

FOOTBALLDATA_API_KEY = os.getenv("FOOTBALLDATA_API_KEY", "")
FD_BASE = "https://api.football-data.org/v4"
_CACHE_TTL = 300  # 5 minutes

_standings_cache: dict = {"data": None, "at": 0.0}


@router.get("/api/standings")
async def get_standings():
    """Proxy WC2026 group standings from football-data.org with a 5-minute cache."""
    now = time.time()
    if _standings_cache["data"] and (now - _standings_cache["at"]) < _CACHE_TTL:
        return _standings_cache["data"]

    if not FOOTBALLDATA_API_KEY:
        return {"groups": [], "error": "API key not configured"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{FD_BASE}/competitions/WC/standings",
                headers={"X-Auth-Token": FOOTBALLDATA_API_KEY},
            )
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:
        logger.warning("Failed to fetch standings: %s", exc)
        # Return stale cache if available
        return _standings_cache["data"] or {"groups": [], "error": "Upstream unavailable"}

    groups = []
    for standing in raw.get("standings", []):
        if standing.get("type") != "TOTAL":
            continue
        group_raw = standing.get("group", "")
        # "GROUP_A" → "Group A",  "GROUP_STAGE" (old format) → skip
        if not group_raw.startswith("GROUP_") or group_raw == "GROUP_STAGE":
            continue
        group_name = "Group " + group_raw.replace("GROUP_", "")
        table = [
            {
                "position": row["position"],
                "team": row["team"]["name"],
                "played": row["playedGames"],
                "won": row["won"],
                "drawn": row["draw"],
                "lost": row["lost"],
                "goals_for": row["goalsFor"],
                "goals_against": row["goalsAgainst"],
                "goal_diff": row["goalDifference"],
                "points": row["points"],
            }
            for row in standing.get("table", [])
        ]
        groups.append({"group": group_name, "table": table})

    result = {"groups": groups}
    _standings_cache["data"] = result
    _standings_cache["at"] = now
    return result


@router.get("/api/bracket")
async def get_bracket(db: AsyncSession = Depends(get_db)):
    """All knockout-stage matches from the DB, grouped by stage."""
    knockout_stages = ["r32", "r16", "qf", "sf", "final"]
    res = await db.execute(
        select(Match)
        .where(Match.stage.in_(knockout_stages))
        .order_by(Match.kickoff_utc)
    )
    matches = res.scalars().all()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    def _status(m: Match) -> str:
        if m.result is not None:
            return "settled"
        if now >= m.kickoff_utc:
            return "closed"
        if now >= m.polls_open_utc:
            return "open"
        return "pending"

    return [
        {
            "id": m.id,
            "stage": m.stage,
            "match_label": m.match_label,
            "team_a": m.team_a or "TBD",
            "team_b": m.team_b or "TBD",
            "kickoff_utc": m.kickoff_utc.isoformat(),
            "status": _status(m),
            "result": m.result,
        }
        for m in matches
    ]
