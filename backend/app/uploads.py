"""
Local file uploads for chat (custom GIFs/images), stored next to the SQLite DB
so they live on the Fly persistent volume (/data/uploads in prod, ./uploads
locally). Kept small via per-file and total-size caps.
"""
import os

from sqlalchemy.engine import make_url

from app.db import DATABASE_URL

MAX_UPLOAD_BYTES = 5 * 1024 * 1024     # 5 MB per file
MAX_TOTAL_BYTES = 400 * 1024 * 1024    # ~400 MB total — keeps the volume usage modest
ALLOWED_EXT = {"gif", "png", "jpg", "jpeg", "webp"}


def upload_dir() -> str:
    """Directory for uploads (created if missing), alongside the SQLite DB file."""
    db_path = make_url(DATABASE_URL).database or "./fifa.db"
    d = os.path.join(os.path.dirname(db_path) or ".", "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def total_upload_bytes() -> int:
    d = upload_dir()
    return sum(
        os.path.getsize(os.path.join(d, f))
        for f in os.listdir(d)
        if os.path.isfile(os.path.join(d, f))
    )
