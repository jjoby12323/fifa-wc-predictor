from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.auth import require_user
from app.models import Message, User, ChatMessage, ChatRequest

router = APIRouter()

MAX_LENGTH = 280


@router.get("/api/chat", response_model=list[ChatMessage])
async def get_messages(db: AsyncSession = Depends(get_db)):
    """Read chat — no auth required so the widget loads on the public leaderboard too."""
    result = await db.execute(
        select(Message, User)
        .join(User, Message.user_id == User.id)
        .order_by(Message.created_at.desc())
        .limit(50)
    )
    rows = result.all()
    return [
        ChatMessage(
            id=msg.id,
            username=user.username,
            display_name=user.display_name,
            content=msg.content,
            created_at=msg.created_at,
        )
        for msg, user in reversed(rows)  # oldest first for display
    ]


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

    msg = Message(
        user_id=user.id,
        content=content,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    return ChatMessage(
        id=msg.id,
        username=user.username,
        display_name=user.display_name,
        content=msg.content,
        created_at=msg.created_at,
    )
