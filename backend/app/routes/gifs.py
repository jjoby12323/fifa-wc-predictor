"""
GIF search proxied from Giphy so the API key stays server-side.

Set GIPHY_API_KEY to enable. When unset, /api/gifs reports {"enabled": false}
and the chat GIF button hides itself — the rest of the chat works unchanged.
Register a free key at https://developers.giphy.com/.
"""
import os
import logging

import httpx
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)

GIPHY_API_KEY = os.getenv("GIPHY_API_KEY", "")
GIPHY_BASE = "https://api.giphy.com/v1/gifs"


@router.get("/api/gifs")
async def search_gifs(q: str = "", limit: int = 18):
    """Search Giphy (or trending when q is empty). Returns small renditions only."""
    if not GIPHY_API_KEY:
        return {"enabled": False, "gifs": []}

    q = q.strip()
    endpoint = "search" if q else "trending"
    params = {"api_key": GIPHY_API_KEY, "limit": max(1, min(limit, 30)), "rating": "pg-13"}
    if q:
        params["q"] = q

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{GIPHY_BASE}/{endpoint}", params=params)
            resp.raise_for_status()
            data = resp.json().get("data", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Giphy request failed: %s", type(exc).__name__)
        return {"enabled": True, "gifs": []}

    gifs = []
    for g in data:
        imgs = g.get("images", {})
        send = (imgs.get("fixed_width") or imgs.get("downsized") or {}).get("url")
        preview = (imgs.get("fixed_width_small") or imgs.get("fixed_width") or {}).get("url") or send
        if send:
            gifs.append({"send": send, "preview": preview})
    return {"enabled": True, "gifs": gifs}
