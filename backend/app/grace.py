"""Admin 'late voting' grace window.

A temporary, in-memory override that lets people vote on matches which have already kicked off
but are NOT settled yet — for the odd case where someone missed the window. It never allows
voting on a settled match (no voting with a known result), and it auto-expires so it can't be
left on by accident. In-memory on purpose: it resets to off on restart, which is fine for a
brief, admin-coordinated window.
"""
from datetime import datetime, timedelta, timezone

DEFAULT_MINUTES = 30
_active_until: datetime | None = None  # UTC-naive


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enable(minutes: int = DEFAULT_MINUTES) -> None:
    global _active_until
    _active_until = _now() + timedelta(minutes=max(1, int(minutes)))


def disable() -> None:
    global _active_until
    _active_until = None


def is_active() -> bool:
    return _active_until is not None and _now() < _active_until


def status() -> dict:
    return {"active": is_active(), "until": (_active_until.isoformat() + "Z") if is_active() else None}
