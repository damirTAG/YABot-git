import time
from random import randrange

from aiogram import Bot, Router, types
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import logger
from config.constants import (
    CLOSE_BUTTON,
    FAILED_BUTTON,
    GENERATING_BUTTON,
    HELP,
    IGNORE_CHAT_IDS,
    INFO,
    MAX_GPT_QUERY_LENGTH,
    PM_BUTTON,
)
from database.cache import cache
from database.repo import DB_actions
from services.makequote import QuoteMaker
from services.openai import generate_response
from utils import RegexFilter, Tools
from utils.decorators import log
from utils.helpers import build_saved_files_keyboard

router = Router()
db = DB_actions()
tools = Tools()


# -- Base commands --


@router.message(CommandStart())
@log("start")
async def hello(message: types.Message):
    start_text = f"""
<b>Welcome! I will help you to download content from the list of services below:</b>

{HELP}
"""

    await message.reply(text=start_text, reply_markup=CLOSE_BUTTON)


@router.message(Command(commands=["roll", "ролл"], prefix="!/."))
@log("roll")
async def rate(message: types.Message):
    if db.get_setting(message.chat.id, "roll_disabled"):
        return

    nick = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>"
    random = randrange(101)
    roll = f"🎱 <b>{nick}</b> роллит! [1-100]. Выпадает: <b>{random}</b>!"
    await message.answer(text=roll, reply_to_message_id=message.message_id)


@router.message(Command(commands=["info", "инфо"], prefix="!/."))
@log("INFO")
async def info_handler(message: types.Message):
    try:
        results = db.execute_query("SELECT video_link FROM video_cache")
        video_links = [row[0] for row in results]
        total_files = len(video_links)

        platform_counts = tools.parse_platforms(video_links)
        sorted_platforms = sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)
        most_downloaded, most_downloaded_count = sorted_platforms.pop(0)

        others = "\n".join(
            [f"• {platform}: {count:,} files" for platform, count in sorted_platforms]
        )

        requests_stats = db.execute_query(""" 
            WITH daily_counts AS (
                SELECT DATE(used_at) as date, COUNT(*) as count
                FROM commands
                GROUP BY DATE(used_at)
            )
            SELECT 
                ROUND(AVG(count), 1) as avg_requests,
                MAX(count) as max_requests,
                DATE(MAX(date)) as last_active_date
            FROM daily_counts;
        """) or [(None, None, None)]
        if requests_stats and len(requests_stats) > 0:
            avg_requests, max_requests, _ = requests_stats[0]
        else:
            avg_requests, max_requests, _ = None, None, None

        avg_requests = avg_requests or 0
        max_requests = max_requests or 0

        ai_cur_stats = db.execute_query(""" 
            SELECT command, COUNT(*) as count
            FROM commands
            WHERE command IN ('ASK', 'CHATGPT', 'SPEECH_REC', 'COINS_CONVERTER')
            GROUP BY command
        """)
        feature_stats = dict(ai_cur_stats)

        ai_answers = feature_stats.get("ASK", 0) + feature_stats.get("CHATGPT", 0)
        speech_count = feature_stats.get("SPEECH_REC", 0)
        currency_conversions = feature_stats.get("COINS_CONVERTER", 0)

        total_users = db.execute_query("SELECT COUNT(DISTINCT user_id) FROM users")[0][0]
        total_chats = db.execute_query("SELECT COUNT(DISTINCT chat_id) FROM chats")[0][0]

        chats_info = f"and {total_chats:,} group chats "

        response = INFO.format(
            most_downloaded=most_downloaded,
            most_downloaded_count=most_downloaded_count,
            others=others,
            ai_answers=ai_answers,
            speech_count=speech_count,
            avg_requests=avg_requests,
            currency_conv=currency_conversions,
            total_files=total_files,
            total_users=total_users,
            chats_info=chats_info,
        )

        await message.reply(response, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error in info_handler: {e}")
        await message.reply("Failed to handle this request, try again later")


@router.message(Command("ask"))
@log("ASK")
async def ask_handler(m: types.Message, command: CommandObject):
    if db.get_setting(m.chat.id, "gpt_disabled"):
        return

    query: str = command.args
    user = m.from_user

    if m.reply_to_message and not query:
        query = m.reply_to_message.text
    if not query:
        return await m.reply("Query is empty. Example use: <code>/ask whats the Pi number?</code>")
    if len(query) > MAX_GPT_QUERY_LENGTH:
        query = query[:MAX_GPT_QUERY_LENGTH].rstrip() + "..."

    temp_msg = await m.reply(
        f"{user.full_name} asking for: <code>{query}</code>", reply_markup=GENERATING_BUTTON
    )
    logger.info(f"{user.full_name} [{user.username}]: Asking for {query}")

    start_time = time.time()
    response = await generate_response(query)
    end_time = time.time()
    taken_time = round(end_time - start_time, 2)

    if response:
        await temp_msg.delete()
        resp_key = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"✅ {taken_time} sec", callback_data="confirmed")]
            ]
        )
        await m.reply(
            f"{user.full_name} asked for: `{query}`\n\n*Answer:*\n{response}",
            reply_markup=resp_key,
            parse_mode="Markdown",
        )
    else:
        await temp_msg.delete()
        await m.reply(
            f"{user.full_name} asked for: `{query}`\n\n*Response failed =(*",
            reply_markup=FAILED_BUTTON,
            parse_mode="Markdown",
        )
    

@router.message(Command("saved"))
@log("SAVED")
async def show_saved_files_handler(m: types.Message):
    user_id = m.from_user.id

    if m.chat.type != "private":
        return await m.reply(
            "This command only works in private chat with the bot.",
            reply_markup=PM_BUTTON,
            disable_web_page_preview=True,
        )

    query = """
        SELECT COUNT(*) FROM user_saved
        WHERE user_id = ?
    """
    result = db.execute_query(query, (user_id,), fetch_all=False)
    total_files = result[0] if result else 0

    if total_files == 0:
        return await m.reply("You don't have any saved files yet.")

    keyboard = build_saved_files_keyboard(user_id)

    await m.reply(
        f"You have {total_files} saved {'file' if total_files == 1 else 'files'}. "
        f"Select one to view:",
        reply_markup=keyboard,
    )


# -- Music platforms search commands --
from services.soundcloud import SoundCloudTool  # noqa: E402
from services.yandexmusic import TrackData, YandexMusicSDK  # noqa: E402

sc = SoundCloudTool()


@router.message(Command("ym"))
@log("YM_TRACK_SEARCH")
async def ym_command_handler(message: types.Message, command: CommandObject):
    args: str = command.args
    if not args:
        return await message.reply(
            "❌ Укажите поисковый запрос. Пример: <code>/ym The Beatles</code>"
        )

    search_msg = await message.reply(f"<b>🔍 Searching:</b> <code>{args}</code>")
    async with YandexMusicSDK() as ym:
        results: list[TrackData] = await ym.search(args, count=10, download=False)
        if not results:
            return await search_msg.edit_text("🚫 Tracks not found =000")

        keyboard_builder = InlineKeyboardBuilder()

        for track in results:
            cache.add_to_cache("yandexmusic", track.id, track)

            keyboard_builder.button(
                text=f"{track.title} - {track.artists}", callback_data=f"yandex_{track.id}"
            )

        keyboard_builder.button(text="❌ Close", callback_data="close")
        keyboard_builder.adjust(1)
        await search_msg.delete()
        await message.reply(
            f"<b>{args.capitalize()}</b>", reply_markup=keyboard_builder.as_markup()
        )


@router.message(Command("sc"))
@log("SC_TRACK_SEARCH")
async def soundsearch(message: types.Message, command: CommandObject):
    chat_id = message.chat.id
    if chat_id in IGNORE_CHAT_IDS:
        return False

    args = command.args
    if not args:
        return await message.reply(
            "❌ Укажите поисковый запрос. Пример: <code>/sc virtual love</code>"
        )

    if not tools.check_query(args):
        return await message.reply("Search query is too long!")

    search_msg = await message.reply(f"<b>🔍 Searching:</b> <code>{args}</code>")

    try:
        results = await sc.search_tracks(args)

        if not results:
            return await search_msg.edit_text("🚫 Tracks not found =000")

        keyboard_builder = InlineKeyboardBuilder()

        for track in results:
            if not track.download_link:
                continue

            cache.add_to_cache("soundcloud", track.track_id, track)

            keyboard_builder.button(
                text=f"{track.title} - {track.artists}", callback_data=f"soundcl_{track.track_id}"
            )

        keyboard_builder.button(text="❌ Close", callback_data="close")
        keyboard_builder.adjust(1)

        await search_msg.delete()
        await message.reply(
            f"<b>{args.capitalize()}</b>", reply_markup=keyboard_builder.as_markup()
        )

    except Exception as e:
        logger.error(f"SoundCloud search error: {e}")


# make quote handler
quote_pattern = r"^[/\.](q|й)$"


@router.message(RegexFilter(quote_pattern))
@log("QUOTE_MAKER")
async def makequote_handler(message: types.Message, bot: Bot):
    if db.get_setting(message.chat.id, "quote_disabled"):
        return

    quotemaker = QuoteMaker(bot)
    await quotemaker.send_quote(message)


# settings handler
SETTINGS_EMOJI = {
    "voice_disabled": "🎤",
    "quote_disabled": "💬",
    "tiktok_send_sound_videos_disabled": "🎵",
    "coins_converter_disabled": "💰",
    "roll_disabled": "🎲",
    "gpt_disabled": "🤖",
    "joke_disabled": "🃏",
}

SETTINGS_NAMES = {
    "voice_disabled": "Voice Messages",
    "tiktok_send_sound_videos_disabled": "TikTok video with Sound",
    "coins_converter_disabled": "Currency Converter",
    "quote_disabled": "Quote Maker (/q)",
    "roll_disabled": "Roll Number (/roll)",
    "gpt_disabled": "AI Responses (/ask)",
    "joke_disabled": "Joke Ratings (/joke)",
}


def get_settings_keyboard(db: DB_actions, chat_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for setting_key in SETTINGS_NAMES.keys():
        is_disabled = db.get_setting(chat_id, setting_key)
        status = "❌" if is_disabled else "✅"
        emoji = SETTINGS_EMOJI[setting_key]
        name = SETTINGS_NAMES[setting_key]

        builder.button(text=f"{emoji} {name}: {status}", callback_data=f"setting:{setting_key}")

    builder.adjust(1)

    builder.row(InlineKeyboardButton(text="Close", callback_data="close", style="danger"))

    return builder.as_markup()


@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    chat_id = message.chat.id

    if message.chat.type in ["group", "supergroup"]:
        user = await message.bot.get_chat_member(chat_id, message.from_user.id)
        if user.status not in ["creator", "administrator"]:
            await message.answer("⚠️ Only administrators can change bot settings in group chats.")
            return

    text = "⚙️ <b>Bot Settings</b>\n\nSelect a feature to enable/disable:"

    keyboard = get_settings_keyboard(db, chat_id)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
