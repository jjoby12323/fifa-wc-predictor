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


def build_round_open_text(round_label: str, fixtures: list[tuple[str, str]], first_date_label: str) -> str:
    n = len(fixtures)
    lines = [
        f":trophy: *{round_label} voting is open!*",
        f"The whole round is up — all {n} match{'es' if n != 1 else ''}, first one {first_date_label}:",
    ]
    lines += [f"   • {a} vs {b}" for a, b in fixtures]
    lines += ["", "Get your picks in before each kicks off. :soccer:"]
    return "\n".join(lines)


def build_final_open_text(fixtures: list[tuple[str, str, str]]) -> str:
    """fixtures: [(round_label, team_a, team_b), ...] for the Final and 3rd-place match."""
    lines = [
        ":trophy: *The Final & 3rd-place match are open for voting!*",
        "Both are worth *4 points* — the biggest calls of the tournament. :fire:",
    ]
    lines += [f"   • {rl}: {a} vs {b}" for rl, a, b in fixtures]
    lines += ["", "Get your picks in before kickoff. :soccer:"]
    return "\n".join(lines)


def build_reminder_text(date_label: str, names: list[str], hours_before: int) -> str:
    people = ", ".join(names)
    return (
        f":alarm_clock: *{hours_before}h to kickoff for {date_label}!*\n"
        f"Still need to pick: {people}\n"
        f"Get your picks in before the whistle. :soccer:"
    )


def build_result_text(team_a: str, team_b: str, result: str,
                      score_a: int | None = None, score_b: int | None = None,
                      stage: str = "group",
                      pens_a: int | None = None, pens_b: int | None = None) -> str:
    have_score = score_a is not None and score_b is not None
    if result == "draw":
        if have_score:
            return f":soccer: Full time: *{team_a}* {score_a}–{score_b} *{team_b}*. :handshake:"
        return f":soccer: Full time: *{team_a}* and *{team_b}* played out a draw. :handshake:"
    if result == "team_a":
        winner, loser, win_goals, lose_goals, win_pens, lose_pens = team_a, team_b, score_a, score_b, pens_a, pens_b
    else:
        winner, loser, win_goals, lose_goals, win_pens, lose_pens = team_b, team_a, score_b, score_a, pens_b, pens_a
    if not have_score:
        return f":soccer: Full time: *{winner}* beat {loser}."
    if win_pens is not None and lose_pens is not None:
        # decided on penalties — lead with the shootout score, level score in brackets
        return f":soccer: Full time: *{winner}* beat {loser} on penalties *{win_pens}–{lose_pens}* ({win_goals}–{lose_goals}). :goal_net:"
    # fallback: a level knockout score we couldn't tally — still flag the shootout
    if win_goals == lose_goals and stage != "group":
        return f":soccer: Full time: *{winner}* beat {loser} on penalties ({win_goals}–{lose_goals}). :goal_net:"
    return f":soccer: Full time: *{winner}* beat {loser} *{win_goals}–{lose_goals}*."


def build_wrapup_text(champion: str, runner_up: str, third_place: str | None,
                      podium: list[dict]) -> str:
    """One-time closing message: World Cup champion + Predictor podium + a thank-you.

    podium: [{'rank': int, 'name': str, 'total': float}, ...] — already ranked, top few.
    """
    third_clause = f", and *{third_place}* took 3rd place" if third_place else ""
    lines = [
        ":trophy: *That's a wrap — FIFA World Cup 2026 is in the books!* :trophy:",
        "",
        f":soccer: *World Champions: {champion}* — they beat {runner_up} in the final{third_clause}.",
        "",
        "And now for the calls that mattered most around here — your Predictor podium :point_down:",
    ]
    medals = {1: ":first_place_medal:", 2: ":second_place_medal:", 3: ":third_place_medal:"}
    for e in podium:
        pts = e["total"]
        prefix = medals.get(e["rank"], f"`{e['rank']}.`")
        lines.append(f"{prefix}  *{e['name']}* — {pts:g} pt{'s' if pts != 1 else ''}")
    lines += [
        "",
        "Take a bow, top three. :bow:",
        "",
        "Huge thanks to *everyone* who played — every pick, every upset shout, and every bit of "
        "trash talk made the last month a blast. Whether you topped the table or just turned up to "
        "back the underdogs, thank you for playing. :heart:",
    ]
    link = _leaderboard_link()
    if link:
        lines += ["", f"<{link}|Final standings →>"]
    lines += ["", "Until the next one — same chaos, fresh bracket. :wave:"]
    return "\n".join(lines)


def build_leaderboard_text(entries: list[dict], title: str = "Standings") -> str:
    """entries: [{'rank': int, 'name': str, 'total': int}, ...] (already ranked)."""
    if not entries or all(e["total"] == 0 for e in entries):
        return f":bar_chart: *{title}* — no points on the board yet. Tournament's just getting started!"
    medals = {1: ":first_place_medal:", 2: ":second_place_medal:", 3: ":third_place_medal:"}
    lines = [f":bar_chart: *{title}*"]
    for e in entries:
        prefix = medals.get(e["rank"], f"`{e['rank']}.`")
        pts = e["total"]
        lines.append(f"{prefix} {e['name']} — *{pts:g}* pt{'s' if pts != 1 else ''}")
    link = _leaderboard_link()
    if link:
        lines += ["", f"<{link}|Full leaderboard →>"]
    return "\n".join(lines)
