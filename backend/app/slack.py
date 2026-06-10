"""
Slack Incoming Webhook integration — outbound only.

Set SLACK_WEBHOOK_URL to enable. When unset, post_to_slack() is a safe no-op,
so the rest of the app behaves identically with or without Slack configured.

This module holds the transport (post_to_slack) plus pure message-formatting
helpers (build_* functions). The helpers take primitive args only — no DB — so
they're trivially unit-testable. Data gathering lives in app/notifications.py.
"""
import os
import logging

import httpx

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
BASE_URL = os.getenv("BASE_URL", "")


def slack_enabled() -> bool:
    return bool(SLACK_WEBHOOK_URL)


async def post_to_slack(text: str) -> bool:
    """POST an mrkdwn message to the configured webhook. No-op (returns False) if unset."""
    if not SLACK_WEBHOOK_URL:
        logger.debug("SLACK_WEBHOOK_URL not set — skipping Slack post.")
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={"text": text})
            resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        # Don't log `exc` itself — httpx errors embed the (secret) webhook URL.
        logger.warning("Slack post failed: %s", type(exc).__name__)
        return False


def _leaderboard_link() -> str:
    return f"{BASE_URL}/leaderboard.html" if BASE_URL else ""


# ── Message builders (pure) ─────────────────────────────────────────────────

def build_polls_open_text(date_label: str, fixtures: list[tuple[str, str]]) -> str:
    n = len(fixtures)
    lines = [
        f":soccer: *Predictions are open for {date_label}!*",
        f"{n} match{'es' if n != 1 else ''} to call:",
    ]
    lines += [f"   • {a} vs {b}" for a, b in fixtures]
    lines += ["", "Open your personal link to lock in your picks. :crystal_ball:"]
    return "\n".join(lines)


def build_reminder_text(date_label: str, names: list[str], hours_before: int) -> str:
    people = ", ".join(names)
    return (
        f":alarm_clock: *{hours_before}h to kickoff for {date_label}!*\n"
        f"Still need to pick: {people}\n"
        f"Get your picks in before the whistle. :soccer:"
    )


def build_result_text(team_a: str, team_b: str, result: str, rank_a: int, rank_b: int) -> str:
    if result == "team_a":
        winner, loser, upset = team_a, team_b, rank_a > rank_b
    else:
        winner, loser, upset = team_b, team_a, rank_b > rank_a
    bolt = "  :zap: *Upset!*" if upset else ""
    return f":soccer: Full time: *{winner}* beat {loser}.{bolt}"


def build_leaderboard_text(entries: list[dict], title: str = "Standings") -> str:
    """entries: [{'rank': int, 'name': str, 'total': int}, ...] (already ranked)."""
    if not entries or all(e["total"] == 0 for e in entries):
        return f":bar_chart: *{title}* — no points on the board yet. Tournament's just getting started!"
    medals = {1: ":first_place_medal:", 2: ":second_place_medal:", 3: ":third_place_medal:"}
    lines = [f":bar_chart: *{title}*"]
    for e in entries:
        prefix = medals.get(e["rank"], f"`{e['rank']}.`")
        pts = e["total"]
        lines.append(f"{prefix} {e['name']} — *{pts}* pt{'s' if pts != 1 else ''}")
    link = _leaderboard_link()
    if link:
        lines += ["", f"<{link}|Full leaderboard →>"]
    return "\n".join(lines)
