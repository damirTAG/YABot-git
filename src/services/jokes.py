"""Weekly joke leaderboard scheduler and message formatting.

Kept separate from the handlers so it can be imported by both the `/joke`
handlers and the background scheduler started in ``app.py`` without import cycles.
"""

import asyncio
import html
from datetime import datetime, timedelta
from typing import Any

import pytz

from config import logger
from database.repo import DB_actions

TZ = pytz.timezone("Asia/Almaty")  # UTC+5
RUN_HOUR = 23
RUN_MINUTE = 40
MIN_VOTERS = 3

db = DB_actions()


def mention(user_id: int, name: str | None) -> str:
    """HTML user mention, safely escaped."""
    return f'<a href="tg://user?id={user_id}">{html.escape(name or "User")}</a>'


def _avg(value: float | None) -> str:
    return f"{value}/10" if value is not None else "—"


def _jokes(n: int) -> str:
    return f"{n} joke" if n == 1 else f"{n} jokes"


# ------------------------------------------------------------- formatting --


def format_awards(awards: dict[str, Any]) -> str:
    if not awards or awards.get("total_jokes", 0) == 0:
        return "🃏 <b>Weekly Joke Awards</b>\n\nNo jokes were rated this week 🦗"

    lines = ["🏆 <b>Weekly Joke Awards</b>", ""]
    best = awards.get("best")
    bullshit = awards.get("bullshit")
    most_active = awards.get("most_active")
    funniest = awards.get("funniest")

    if best:
        lines.append(
            f"🏆 Best joker: {mention(best['author_id'], best['author_name'])} "
            f"— avg {best['avg']}/10 ({_jokes(best['jokes'])})"
        )
    if bullshit:
        lines.append(
            f"💩 Most bullshit: {mention(bullshit['author_id'], bullshit['author_name'])} "
            f"— avg {bullshit['avg']}/10"
        )
    if most_active:
        lines.append(
            f"🎤 Most active: {mention(most_active['author_id'], most_active['author_name'])} "
            f"— {_jokes(most_active['jokes'])}"
        )
    if funniest:
        lines.append(
            f"⭐ Funniest joke: {mention(funniest['author_id'], funniest['author_name'])} "
            f"— {funniest['avg']}/10 ({funniest['voters']} votes)"
        )

    if not (best or funniest):
        lines.append(f"<i>(No joke reached {MIN_VOTERS} votes — no top awards this week.)</i>")

    lines.append("")
    lines.append(f"<i>{_jokes(awards['total_jokes'])} rated this week. See you next Sunday!</i>")
    return "\n".join(lines)


def format_leaderboard(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return (
            "📊 <b>This week's leaderboard</b>\n\n"
            f"No qualifying jokes yet (need ≥{MIN_VOTERS} votes per joke)."
        )
    medals = ["🥇", "🥈", "🥉"]
    lines = ["📊 <b>This week's leaderboard</b>", ""]
    for i, r in enumerate(rows):
        rank = medals[i] if i < len(medals) else f"{i + 1}."
        lines.append(
            f"{rank} {mention(r['author_id'], r['author_name'])} "
            f"— {r['avg']}/10 ({_jokes(r['jokes'])})"
        )
    return "\n".join(lines)


def format_user_stats(user_id: int, name: str | None, stats: dict[str, Any]) -> str:
    return (
        f"🃏 <b>{mention(user_id, name)}'s joke stats</b>\n\n"
        f"This week: {_jokes(stats['jokes_week'])} · avg {_avg(stats['avg_week'])}\n"
        f"All time: {_jokes(stats['jokes_all'])} · {stats['votes_received']} votes received "
        f"· avg {_avg(stats['avg_all'])}\n"
        f"Best joke: {_avg(stats['best_avg'])} · Worst: {_avg(stats['worst_avg'])}"
    )


# --------------------------------------------------------------- schedule --


def _next_run(now: datetime) -> datetime:
    """Next Sunday 23:40 Almaty strictly after ``now``."""
    days_ahead = (6 - now.weekday()) % 7  # Monday=0 .. Sunday=6
    candidate = (now + timedelta(days=days_ahead)).replace(
        hour=RUN_HOUR, minute=RUN_MINUTE, second=0, microsecond=0
    )
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def _prev_run(now: datetime) -> datetime:
    """Most recent Sunday 23:40 Almaty at or before ``now``."""
    days_since = (now.weekday() - 6) % 7
    candidate = (now - timedelta(days=days_since)).replace(
        hour=RUN_HOUR, minute=RUN_MINUTE, second=0, microsecond=0
    )
    if candidate > now:
        candidate -= timedelta(days=7)
    return candidate


async def run_weekly_tally(bot, week_end: str) -> None:
    """Post the weekly leaderboard to every active, enabled chat (idempotent)."""
    for chat_id in db.get_active_joke_chats():
        try:
            if db.weekly_run_exists(chat_id, week_end):
                continue
            if db.get_setting(chat_id, "joke_disabled"):
                db.mark_weekly_run(chat_id, week_end)
                continue
            awards = db.get_weekly_awards(chat_id, MIN_VOTERS)
            if awards.get("total_jokes", 0) > 0:
                await bot.send_message(chat_id, format_awards(awards))
            db.mark_weekly_run(chat_id, week_end)
            logger.info(f"[jokes] Posted weekly awards to chat {chat_id} (week {week_end})")
        except Exception as e:
            logger.error(f"[jokes] Failed weekly awards for chat {chat_id}: {e}")


async def weekly_joke_scheduler(bot) -> None:
    """Background task: catch up on a missed run, then post every Sunday 23:40 Almaty."""
    logger.info("[jokes] Weekly scheduler started")
    # Catch-up: if we were down over the last slot, post it now (idempotent).
    try:
        await run_weekly_tally(bot, _prev_run(datetime.now(TZ)).date().isoformat())
    except Exception as e:
        logger.error(f"[jokes] Catch-up tally failed: {e}")

    while True:
        now = datetime.now(TZ)
        target = _next_run(now)
        await asyncio.sleep(max(1.0, (target - now).total_seconds()))
        await run_weekly_tally(bot, target.date().isoformat())
