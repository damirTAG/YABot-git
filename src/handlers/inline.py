import os
import shutil
import time
import uuid

from aiogram import Bot, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import logger
from config.constants import (
    CACHE_CHAT,
    DOWNLOADING_BUTTON,
    FAILED_BUTTON,
    GENERATING_BUTTON,
    MAX_GPT_QUERY_LENGTH,
)
from config.enums import Patterns
from config.settings import BASE_DIR
from database.repo import DB_actions
from services.downloader import download_single_video
from services.openai import generate_response
from utils.decorators import log

router = Router()
db = DB_actions()


user_queries: dict = {}

# Inline download state:
#   download_queries: result_id -> raw link, set on inline_query, consumed on choose.
#   Ready video file_ids are cached in the DB (db.get_inline_file / save_inline_file).
download_queries: dict[str, str] = {}

DOWNLOADING_IMG_PATH = os.path.join(BASE_DIR.parent, "assets", "download_placeholder.png")
_downloading_doc_id: str | None = None


def _is_downloadable_link(text: str) -> bool:
    """True if the inline query is a single-object TikTok video or Instagram reel."""
    text = (text or "").strip()
    return bool(Patterns.TIKTOK.value.match(text) or Patterns.INST_REELS.value.match(text))


async def _get_placeholder_id(bot: Bot) -> str | None:
    """Lazily upload the placeholder once (as a document) and cache its file_id.

    A *document* result renders as a clean text row in the inline dropdown (title
    + description, no gallery image), which makes the action obvious. It's still
    media, so the chosen handler can edit it into a video via editMessageMedia.
    """
    global _downloading_doc_id
    if _downloading_doc_id:
        return _downloading_doc_id
    try:
        msg = await bot.send_document(CACHE_CHAT, types.FSInputFile(DOWNLOADING_IMG_PATH))
        _downloading_doc_id = msg.document.file_id
        return _downloading_doc_id
    except Exception as e:
        logger.error(f"[inline:download] Failed to upload placeholder document: {e}")
        return None


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
async def inline_download_query(inline_query: types.InlineQuery, bot: Bot):
    """Offer a single placeholder result for a raw TikTok/Instagram-reel link.

    If we already downloaded this link in this process, answer instantly with the
    cached video; otherwise show the 'downloading...' photo and let the chosen
    handler swap in the real video.
    """
    link = inline_query.query.strip()
    result_id = uuid.uuid4().hex[:8]

    cached_file_id = db.get_inline_file(link)
    if cached_file_id:
        item = types.InlineQueryResultCachedVideo(
            id=result_id,
            video_file_id=cached_file_id,
            title="Send video",
            caption="📹 <i>downloaded @yerzhanakh_bot</i>",
        )
        return await bot.answer_inline_query(
            inline_query.id, results=[item], cache_time=0, is_personal=True
        )

    placeholder_id = await _get_placeholder_id(bot)
    if not placeholder_id:
        # No placeholder available — nothing to offer, but don't error out.
        return await bot.answer_inline_query(inline_query.id, results=[], cache_time=0)

    download_queries[result_id] = link
    # Document result -> renders as a text row in the dropdown (no gallery image),
    # but is still media so it can be edited into a video once downloaded.
    item = types.InlineQueryResultCachedDocument(
        id=result_id,
        document_file_id=placeholder_id,
        title="📥 Download video",
        description="Tap to fetch the video — takes a few seconds",
        caption="⏳ <i>Downloading...</i>",
        reply_markup=DOWNLOADING_BUTTON,  # required so we receive inline_message_id
    )
    await bot.answer_inline_query(inline_query.id, results=[item], cache_time=0, is_personal=True)


@router.chosen_inline_result(lambda c: _is_downloadable_link(c.query))
@log("INLINE_DOWNLOAD")
async def inline_download_chosen(chosen: types.ChosenInlineResult, bot: Bot):
    """Download the link, upload it to get a file_id, and edit the placeholder."""
    inline_message_id = chosen.inline_message_id
    link = download_queries.pop(chosen.result_id, None)

    # Cache hit path already sent a real video; nothing to do.
    if not link or not inline_message_id:
        return

    download_dir = os.path.join("./temp_downloads", f"inline_{chosen.result_id}")
    try:
        path = await download_single_video(link, download_dir)
        if not path:
            return await bot.edit_message_caption(
                inline_message_id=inline_message_id,
                caption=(
                    "❌ Couldn't download this — it may have multiple items or be unsupported. "
                    "Open @yerzhanakh_bot directly."
                ),
                reply_markup=FAILED_BUTTON,
            )

        # Inline messages can't take an uploaded file — upload once to the cache
        # chat to obtain a reusable file_id, then edit the placeholder into it.
        sent = await bot.send_video(CACHE_CHAT, types.FSInputFile(path), supports_streaming=True)
        file_id = sent.video.file_id
        db.save_inline_file(link, file_id)

        await bot.edit_message_media(
            inline_message_id=inline_message_id,
            media=types.InputMediaVideo(
                media=file_id, caption="📹 <i>downloaded @yerzhanakh_bot</i>"
            ),
        )
        logger.info(f"[inline:download] Sent video for {link}")

    except Exception as e:
        logger.exception(f"[inline:download] Failed for {link}: {e}")
        try:
            await bot.edit_message_caption(
                inline_message_id=inline_message_id,
                caption="❌ Something went wrong while downloading.",
                reply_markup=FAILED_BUTTON,
            )
        except Exception:
            pass
    finally:
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir, ignore_errors=True)


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
