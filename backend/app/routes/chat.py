import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.auth import require_user
from app.models import Message, User, ChatMessage, ChatRequest
from app.uploads import upload_dir, total_upload_bytes, MAX_UPLOAD_BYTES, MAX_TOTAL_BYTES, ALLOWED_EXT

router = APIRouter()

MAX_LENGTH = 280


@router.post("/api/chat/upload")
async def upload_image(file: UploadFile = File(...), _username: str = Depends(require_user)):
    """Save a user-supplied GIF/image to the volume and return its URL to post in chat."""
    ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
    if ext not in ALLOWED_EXT or not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Only GIF, PNG, JPG, or WebP images are allowed.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).")
    if total_upload_bytes() + len(data) > MAX_TOTAL_BYTES:
        raise HTTPException(status_code=507, detail="Upload storage is full — ask the admin to clear some space.")
    name = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(upload_dir(), name), "wb") as f:
        f.write(data)
    return {"url": f"/uploads/{name}"}


@router.get("/api/chat", response_model=list[ChatMessage])
async def get_messages(db: AsyncSession = Depends(get_db)):
    """Read chat — no auth required so the widget loads on the public leaderboard too."""
    result = await db.execute(
        select(Message, User)
        .join(User, Message.user_id == User.id)
        .order_by(Message.created_at.desc())
        .limit(50)
    )
    rows = list(reversed(result.all()))  # oldest first for display

    # Resolve the quoted (replied-to) messages — they may be older than the 50 shown.
    reply_ids = {msg.reply_to_id for msg, _ in rows if msg.reply_to_id}
    quoted: dict[int, tuple[str, str]] = {}
    if reply_ids:
        ref = await db.execute(
            select(Message, User).join(User, Message.user_id == User.id).where(Message.id.in_(reply_ids))
        )
        for m, u in ref.all():
            quoted[m.id] = (u.display_name, m.content)

    out = []
    for msg, user in rows:
        rn, rc = quoted.get(msg.reply_to_id, (None, None))
        out.append(ChatMessage(
            id=msg.id,
            username=user.username,
            display_name=user.display_name,
            content=msg.content,
            created_at=msg.created_at,
            reply_to_id=msg.reply_to_id if rn is not None else None,
            reply_to_name=rn,
            reply_to_content=rc,
        ))
    return out


@router.post("/api/chat", response_model=ChatMessage)
async def post_message(
    body: ChatRequest,
    username: str = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(content) > MAX_LENGTH:
        raise HTTPException(status_code=400, detail=f"Max {MAX_LENGTH} characters.")

    user_result = await db.execute(select(User).where(User.username == username))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    # Validate the reply target (ignore silently if it doesn't exist).
    ref_row = None
    if body.reply_to is not None:
        ref = await db.execute(
            select(Message, User).join(User, Message.user_id == User.id).where(Message.id == body.reply_to)
        )
        ref_row = ref.first()
    reply_to_id = body.reply_to if ref_row else None

    msg = Message(
        user_id=user.id,
        content=content,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        reply_to_id=reply_to_id,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    rn = rc = None
    if ref_row:
        rmsg, ruser = ref_row
        rn, rc = ruser.display_name, rmsg.content

    return ChatMessage(
        id=msg.id,
        username=user.username,
        display_name=user.display_name,
        content=msg.content,
        created_at=msg.created_at,
        reply_to_id=reply_to_id,
        reply_to_name=rn,
        reply_to_content=rc,
    )
