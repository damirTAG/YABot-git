import time
import uuid

from aiogram import Bot, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import logger
from config.constants import FAILED_BUTTON, GENERATING_BUTTON, MAX_GPT_QUERY_LENGTH
from config.enums import Patterns
from database.repo import DB_actions
from services.downloader import resolve_inline_media
from services.openai import generate_response
from utils.decorators import log

router = Router()
db = DB_actions()


user_queries: dict = {}


def _is_downloadable_link(text: str) -> bool:
    """True if the inline query is a TikTok or Instagram reel link."""
    text = (text or "").strip()
    return bool(Patterns.TIKTOK.value.match(text) or Patterns.INST_REELS.value.match(text))


@router.inline_query(lambda query: query.query.lower().startswith("ask "))
async def chatgpt_inline_handler(inline_query: types.InlineQuery, bot: Bot):
    user_input = inline_query.query[4:].strip()
    if len(user_input) > MAX_GPT_QUERY_LENGTH:
        user_input = user_input[:MAX_GPT_QUERY_LENGTH].rstrip() + "..."
    user = inline_query.from_user

    if len(user_input) < 3:
        return

    try:
        result_id = uuid.uuid4().hex[:8]
        user_queries[result_id] = user.full_name, user_input
        item = types.InlineQueryResultArticle(
            id=result_id,
            title="Answer from AI",
            description=f"Asking for: {user_input}",
            input_message_content=types.InputTextMessageContent(
                message_text=f"{user.full_name} asking for: <code>{user_input}</code>"
            ),
            reply_markup=GENERATING_BUTTON,
        )

        await bot.answer_inline_query(inline_query.id, results=[item], cache_time=0)
        logger.info(f"{user.full_name} [{user.username}]: Asking for {user_input}")

    except Exception as e:
        logger.error(f"Error in inline handler: {e}")


@router.chosen_inline_result(lambda chosen: chosen.query.lower().startswith("ask "))
@log("CHATGPT")
async def chatgpt_chosen_inline_handler(chosen_inline_query: types.ChosenInlineResult, bot: Bot):
    try:
        message_id = chosen_inline_query.inline_message_id
        result_id = chosen_inline_query.result_id

        if result_id not in user_queries:
            return

        user_name, user_prompt = user_queries[result_id]

        start_time = time.time()
        response = await generate_response(user_prompt)
        end_time = time.time()
        taken_time = round(end_time - start_time, 2)

        if response:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=f"✅ {taken_time} sec", callback_data="confirmed")]
                ]
            )
            await bot.edit_message_text(
                inline_message_id=message_id,
                text=f"{user_name} asked for: `{user_prompt}`\n\n*Answer:*\n{response}",
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        else:
            await bot.edit_message_text(
                inline_message_id=message_id,
                text=f"{user_name} asked for: `{user_prompt}`\n\n*Response failed =(*",
                parse_mode="Markdown",
                reply_markup=FAILED_BUTTON,
            )
        del user_queries[result_id]

    except Exception as e:
        logger.error(f"Error in chosen inline handler: {e}")


@router.inline_query(lambda q: _is_downloadable_link(q.query))
@log("INLINE_DOWNLOAD")
async def inline_download_query(inline_query: types.InlineQuery, bot: Bot):
    """Resolve a TikTok/Instagram link to direct CDN URLs and answer inline.

    Cobalt/tikwm hand back public CDN URLs (``status: redirect``), so we let
    Telegram fetch them itself via ``InlineQueryResult*`` — no placeholder, no
    download, no file_id. Carousels become several results the user can pick from.
    """
    link = inline_query.query.strip()

    try:
        media = await resolve_inline_media(link)
    except Exception as e:
        logger.exception(f"[inline:download] Resolve failed for {link}: {e}")
        media = []

    results = []
    for item in media:
        result_id = uuid.uuid4().hex[:8]
        if item["type"] == "video":
            results.append(
                types.InlineQueryResultVideo(
                    id=result_id,
                    video_url=item["url"],
                    mime_type="video/mp4",
                    thumbnail_url=item["thumb"],
                    title="📥 download video",
                    caption=f"<a href='{link}'>📹 downloaded by</a> @yerzhanakh_bot",
                )
            )
        else:  # photo
            results.append(
                types.InlineQueryResultPhoto(
                    id=result_id,
                    photo_url=item["url"],
                    thumbnail_url=item["thumb"],
                    title="📥 download photo",
                    caption=f"<a href='{link}'>🖼 downloaded by</a> @yerzhanakh_bot",
                )
            )

    await bot.answer_inline_query(inline_query.id, results=results, cache_time=10)


# Fix for general inline handler
@router.inline_query()
async def inline_get_file(query: types.InlineQuery):
    PAGE_SIZE = 50
    user_id = query.from_user.id
    offset = int(query.offset) if query.offset else 0

    files = db.execute_query(
        "SELECT file_id, type FROM user_saved WHERE user_id = ? LIMIT ? OFFSET ?",
        (user_id, PAGE_SIZE, offset),
    )

    if files:
        print(f"User_id: {user_id} Found {len(files)}")

    results = []
    for file_id, file_type in files:
        res_id = uuid.uuid4().hex[:8]
        if file_type.startswith("video"):
            result = types.InlineQueryResultCachedVideo(
                id=res_id, video_file_id=file_id, title="Saved Video"
            )
        elif file_type.startswith("audio"):
            result = types.InlineQueryResultCachedAudio(id=res_id, audio_file_id=file_id)
        elif file_type.startswith("voice"):
            result = types.InlineQueryResultCachedVoice(
                id=res_id, voice_file_id=file_id, title="Saved Voice"
            )
        else:
            result = types.InlineQueryResultCachedDocument(
                id=res_id, document_file_id=file_id, title="Saved Doc"
            )

        results.append(result)

    next_offset = str(offset + PAGE_SIZE) if len(files) == PAGE_SIZE else ""

    await query.answer(results, cache_time=1, is_personal=True, next_offset=next_offset)
