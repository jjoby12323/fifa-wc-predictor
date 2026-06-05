"""
One-time setup: creates tables, syncs fixtures, inserts users.
Safe to re-run (idempotent).

Usage:
    cd backend
    python seed.py
"""
import asyncio
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from app.db import engine, Base


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created (or already exist).")


async def main():
    await create_tables()
    print("\nNext steps:")
    print("  1. python -m scripts.sync_fixtures   # pull WC2026 matches from football-data.org")
    print("  2. python -m scripts.generate_links  # create users + print signed URLs")


if __name__ == "__main__":
    asyncio.run(main())
