import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import matches, votes, leaderboard, admin, chat, profile, standings, gifs
from app.sync import start_result_scheduler, stop_result_scheduler
from app.db import engine
from app.uploads import upload_dir


async def _ensure_schema():
    """Additive, idempotent column adds for the live DB. Deploys don't run Alembic,
    so make sure newer columns exist on the existing tables (SQLite ADD COLUMN is
    safe and a no-op once present / on a fresh DB)."""
    def _apply(conn):
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(messages)").fetchall()]
        if cols and "reply_to_id" not in cols:
            conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN reply_to_id INTEGER")
    async with engine.begin() as conn:
        await conn.run_sync(_apply)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_schema()
    start_result_scheduler()
    yield
    stop_result_scheduler()


app = FastAPI(title="FIFA WC 2026 Predictor", lifespan=lifespan)

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
origins = [o.strip() for o in allowed_origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches.router)
app.include_router(votes.router)
app.include_router(leaderboard.router)
app.include_router(admin.router)
app.include_router(chat.router)
app.include_router(profile.router)
app.include_router(standings.router)
app.include_router(gifs.router)

# Serve user-uploaded chat images from the data volume (created on first use).
app.mount("/uploads", StaticFiles(directory=upload_dir()), name="uploads")

# Works both locally (../../frontend) and in Docker (/app/frontend)
for _candidate in [
    os.path.join(os.path.dirname(__file__), "..", "frontend"),       # Docker: /app/frontend
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend"),  # local dev
]:
    if os.path.isdir(_candidate):
        app.mount("/", StaticFiles(directory=_candidate, html=True), name="frontend")
        break
