"""
Manual seed: pull all WC 2026 fixtures from football-data.org and upsert them.
Run once before the tournament (or to backfill). Ongoing updates happen
automatically via the scheduled fixture sync in app/sync.py.

Usage:
    cd backend
    python -m scripts.sync_fixtures
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.fixtures import sync_fixtures

if __name__ == "__main__":
    if not os.getenv("FOOTBALLDATA_API_KEY"):
        print("Error: FOOTBALLDATA_API_KEY not set in .env")
        sys.exit(1)
    print("Fetching WC 2026 fixtures from football-data.org...")
    n = asyncio.run(sync_fixtures(set_results=True))
    print(f"Done. {n} fixtures synced.")
