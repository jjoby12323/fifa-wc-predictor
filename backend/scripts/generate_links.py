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

PARTICIPANTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "participants.txt")


def load_participants() -> list[str]:
    if not os.path.exists(PARTICIPANTS_FILE):
        print(f"Error: participants.txt not found at {PARTICIPANTS_FILE}")
        print("Create it with one full name per line, e.g.:")
        print("  Jonathan Joby")
        print("  Saral Hemnani")
        sys.exit(1)
    names = [line.strip() for line in open(PARTICIPANTS_FILE) if line.strip()]
    if not names:
        print("Error: participants.txt is empty.")
        sys.exit(1)
    return names


async def generate():
    participants = load_participants()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        for display_name in participants:
            username = display_name.lower().replace(" ", "-")
            existing = await db.execute(select(User).where(User.username == username))
            if existing.scalar_one_or_none() is None:
                db.add(User(username=username, display_name=display_name))
        await db.commit()

    print("\nPersonal vote links (share each privately):\n")
    for display_name in participants:
        username = display_name.lower().replace(" ", "-")
        sig = make_sig(username)
        url = f"{BASE_URL}/?user={username}&sig={sig}"
        print(f"  {display_name:<25}  {url}")

    leaderboard_url = f"{BASE_URL}/leaderboard.html"
    print(f"\nLeaderboard (shareable with everyone):\n  {leaderboard_url}\n")


if __name__ == "__main__":
    asyncio.run(generate())
