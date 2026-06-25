from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import logger
from database.repo import DB_actions
from services.jokes import format_leaderboard, format_user_stats, mention
from utils.decorators import log

router = Router()
db = DB_actions()

GROUP_TYPES = ("group", "supergroup")
MAX_SCORE = 10


def _vote_keyboard(joke_id: int):
    builder = InlineKeyboardBuilder()
    for score in range(MAX_SCORE + 1):
        builder.button(text=str(score), callback_data=f"jvote:{joke_id}:{score}")
    builder.adjust(6, 5)
    return builder.as_markup()


def _poll_text(author_id: int, author_name: str | None, count: int, avg: float) -> str:
    return (
        "🃏 <b>Rate this joke!</b>\n"
        f"By {mention(author_id, author_name)}\n"
        "Tap a button to rate it from 0 to 10.\n\n"
        f"🗳 Votes: {count} · ⭐ Avg: {avg}/10"
    )


@router.message(Command("joke"))
@log("JOKE")
async def cmd_joke(message: types.Message, bot: Bot):
    if message.chat.type not in GROUP_TYPES:
        return await message.reply("🃏 The joke game works in group chats only.")
    if db.get_setting(message.chat.id, "joke_disabled"):
        return

    target = message.reply_to_message
    if not target:
        return await message.reply("Reply to a message with /joke to start a rating poll.")

    author = target.from_user
    if not author or author.is_bot:
        return await message.reply("Reply to a real user's message to rate their joke.")

    name = author.full_name or author.username or "User"
    joke_id = db.create_joke(message.chat.id, author.id, name, target.message_id)
    if not joke_id:
        return await message.reply("Failed to start the poll, try again later.")

    poll = await bot.send_message(
        message.chat.id,
        _poll_text(author.id, name, 0, 0.0),
        reply_to_message_id=target.message_id,
        reply_markup=_vote_keyboard(joke_id),
    )
    db.set_joke_poll_message(joke_id, poll.message_id)


@router.callback_query(F.data.startswith("jvote:"))
async def cb_vote(call: types.CallbackQuery):
    try:
        _, joke_id_s, score_s = call.data.split(":")
        joke_id, score = int(joke_id_s), int(score_s)
    except ValueError:
        return await call.answer("Invalid vote.")

    if not 0 <= score <= MAX_SCORE:
        return await call.answer("Invalid score.")

    joke = db.get_joke(joke_id)
    if not joke:
        return await call.answer("This poll has expired.", show_alert=True)
    if db.get_setting(joke["chat_id"], "joke_disabled"):
        return await call.answer("Joke ratings are disabled in this chat.", show_alert=True)
    if call.from_user.id == joke["author_id"]:
        return await call.answer("😄 You can't rate your own joke!", show_alert=True)

    db.upsert_vote(joke_id, call.from_user.id, score)
    count, avg = db.get_joke_vote_summary(joke_id)

    try:
        await call.message.edit_text(
            _poll_text(joke["author_id"], joke["author_name"], count, avg),
            reply_markup=_vote_keyboard(joke_id),
        )
    except Exception as e:
        # e.g. "message is not modified" when the rating is unchanged.
        logger.debug(f"[jokes] poll edit skipped: {e}")

    await call.answer(f"You rated {score}/10 👍")


@router.message(Command("jokestats"))
@log("JOKE_STATS")
async def cmd_jokestats(message: types.Message):
    if message.chat.type not in GROUP_TYPES:
        return await message.reply("🃏 Joke stats work in group chats only.")
    if db.get_setting(message.chat.id, "joke_disabled"):
        return

    target_user = (
        message.reply_to_message.from_user
        if message.reply_to_message and message.reply_to_message.from_user
        else message.from_user
    )
    name = target_user.full_name or target_user.username or "User"  # type: ignore

    stats = db.get_user_joke_stats(message.chat.id, target_user.id)
    leaderboard = db.get_chat_leaderboard(message.chat.id)
    text = f"{format_user_stats(target_user.id, name, stats)}\n\n{format_leaderboard(leaderboard)}"
    await message.reply(text)
