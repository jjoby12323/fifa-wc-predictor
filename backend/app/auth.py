import hmac
import hashlib
import os
from fastapi import HTTPException, Query

SECRET_KEY = os.getenv("SECRET_KEY", "")


def make_sig(username: str) -> str:
    return hmac.new(SECRET_KEY.encode(), username.encode(), hashlib.sha256).hexdigest()


def verify_sig(username: str, sig: str) -> bool:
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY not set")
    expected = make_sig(username)
    return hmac.compare_digest(expected, sig)


def require_user(
    user: str = Query(..., description="Your username"),
    sig: str = Query(..., description="HMAC signature from your personal link"),
):
    if not verify_sig(user, sig):
        raise HTTPException(status_code=401, detail="Invalid or tampered link.")
    return user
