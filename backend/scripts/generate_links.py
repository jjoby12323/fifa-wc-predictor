"""
Generate one signed URL per participant and insert them into the users table.

Usage:
    cd backend
    python -m scripts.generate_links

Edit PARTICIPANTS below before running.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.auth import make_sig
from app.db import engine, SessionLocal, Base
from app.models import User
from sqlalchemy import select

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# ── Edit this list before running ─────────────────────────────────────────────
PARTICIPANTS = [
    {"username": "alice", "display_name": "Alice"},
    {"username": "bob", "display_name": "Bob"},
    {"username": "carol", "display_name": "Carol"},
    {"username": "dave", "display_name": "Dave"},
    {"username": "eve", "display_name": "Eve"},
    {"username": "frank", "display_name": "Frank"},
    {"username": "grace", "display_name": "Grace"},
    {"username": "henry", "display_name": "Henry"},
    {"username": "isla", "display_name": "Isla"},
]
# ─────────────────────────────────────────────────────────────────────────────


async def generate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        for p in PARTICIPANTS:
            existing = await db.execute(select(User).where(User.username == p["username"]))
            if existing.scalar_one_or_none() is None:
                db.add(User(username=p["username"], display_name=p["display_name"]))
        await db.commit()

    print("\nPersonal vote links (share each privately):\n")
    for p in PARTICIPANTS:
        sig = make_sig(p["username"])
        url = f"{BASE_URL}/?user={p['username']}&sig={sig}"
        print(f"  {p['display_name']:<20}  {url}")

    leaderboard_url = f"{BASE_URL}/leaderboard.html"
    print(f"\nLeaderboard (shareable with everyone):\n  {leaderboard_url}\n")


if __name__ == "__main__":
    asyncio.run(generate())
