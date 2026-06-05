"""
Reset the leaderboard for local testing.

Usage:
    python -m scripts.reset            # wipe votes + scores + results (keep users & fixtures)
    python -m scripts.reset --all      # wipe everything (re-run sync_fixtures + generate_links after)
"""
import asyncio
import sys
import os
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import update, delete
from app.db import SessionLocal
from app.models import Vote, Score, Match, User


async def reset(full=False):
    async with SessionLocal() as db:
        await db.execute(delete(Score))
        await db.execute(delete(Vote))
        await db.execute(update(Match).values(result=None))
        print("Cleared: votes, scores, match results.")

        if full:
            await db.execute(delete(Match))
            await db.execute(delete(User))
            print("Cleared: matches, users.")
            print("Re-run sync_fixtures and generate_links to restore.")

        await db.commit()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(reset(full="--all" in sys.argv))
