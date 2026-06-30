import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Request
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
        mcols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(matches)").fetchall()]
        if mcols and "score_a" not in mcols:
            conn.exec_driver_sql("ALTER TABLE matches ADD COLUMN score_a INTEGER")
        if mcols and "score_b" not in mcols:
            conn.exec_driver_sql("ALTER TABLE matches ADD COLUMN score_b INTEGER")
        if mcols and "pens_a" not in mcols:
            conn.exec_driver_sql("ALTER TABLE matches ADD COLUMN pens_a INTEGER")
        if mcols and "pens_b" not in mcols:
            conn.exec_driver_sql("ALTER TABLE matches ADD COLUMN pens_b INTEGER")
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

@app.middleware("http")
async def cache_control(request: Request, call_next):
    """Make deploys show up on the next reload without users clearing their cache.

    HTML/JS/CSS use `no-cache` — the browser revalidates every load (cheap 304 when
    unchanged, fresh 200 right after a deploy). The dynamic API is never cached, and
    the immutable uploaded files are cached long-term.
    """
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/uploads/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith("/api/") or path.startswith("/admin/"):
        response.headers["Cache-Control"] = "no-store"
    else:
        response.headers["Cache-Control"] = "no-cache"
    return response


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
