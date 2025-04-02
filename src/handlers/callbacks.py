import logging, os, traceback, random

from aiogram                import Router, F, types, Bot

from utils                  import Tools
from config.constants       import (
    CACHE_CHAT, SAVE_BUTTON, CLOSE_BUTTON, 
    COOL_PHRASES, SAVE_BUTTON, SAVED, SAVED_BUTTON
)
from database.repo          import DB_actions
from database.cache         import Base as basecache

from services.yandexmusic   import YandexMusicSDK, TrackData
from services.soundcloud    import SoundCloudTool

logger  = logging.getLogger()
router  = Router()

db      = DB_actions()
cache   = basecache()

tools   = Tools()
sc      = SoundCloudTool()

# -- base callbacks --
@router.callback_query(F.data == "close")
async def close(call: types.CallbackQuery, bot: Bot):
    await bot.delete_message(call.message.chat.id, call.message.message_id)

@router.callback_query(F.data.in_(["waiting", "confirmed"]))
async def waiting(call: types.CallbackQuery):
    await call.answer(
        random.choice(COOL_PHRASES).lower()[:200], True
    )

@router.callback_query(F.data == 'save')
async def save(call: types.CallbackQuery):
    user_id = call.from_user.id
    if call.message.audio:
        file_id = call.message.audio.file_id
        file_type = call.message.audio.mime_type
    elif call.message.voice:
        file_id = call.message.voice.file_id
        file_type = "voice/ogg"
    elif call.message.video:
        file_id = call.message.video.file_id
        file_type = call.message.video.mime_type
    elif call.message.document:
        file_id = call.message.document.file_id
        file_type = call.message.document.mime_type

    try:
        existing_file = db.execute_query("SELECT 1 FROM user_saved WHERE user_id = ? AND file_id = ?", (user_id, file_id))

        if existing_file:
            db.execute_query("DELETE FROM user_saved WHERE user_id = ? AND file_id = ?", (user_id, file_id))

            await call.answer(f"{file_type.split('/')[0].capitalize()} successfully deleted", show_alert=True)
            await call.message.edit_reply_markup(reply_markup=SAVE_BUTTON)
            logging.info(f"File {file_type} deleted for user {user_id}")
        else:
            # File does not exist -> Save it
            db.save_file(user_id, file_id, file_type)

            await call.answer(
                SAVED.format(file_type.split("/")[0]), True
            )
            await call.message.edit_reply_markup(
                reply_markup=SAVED_BUTTON
            )
            logging.info(f"File {file_type} saved for user {user_id}")

    except Exception as e:
        await call.answer("Failed to process file", show_alert=True)
        logging.error(f"Error handling file {file_type} for user {user_id}: {e}")

# -- platforms callbacks

@router.callback_query(F.data.startswith("yandex_"))
async def download_yandex_track(callback_query: types.CallbackQuery, bot: Bot):
    track_id = callback_query.data[len("yandex_"):]
    track: TrackData = cache.get_from_cache("yandexmusic", track_id)
    file_path = None

    if not track:
        return await bot.send_message(callback_query.from_user.id, "🚫 Track not found.")
    msg = callback_query.message  # get Message
    try:
        from_chat_id, from_message_id = db.get_cached_media(url=track.id)
        
        if from_chat_id and from_message_id:
            await bot.copy_message(
                chat_id=callback_query.message.chat.id,
                from_chat_id=from_chat_id,
                message_id=from_message_id,
                reply_markup=SAVE_BUTTON if callback_query.message.chat.type == 'private' else None,
                reply_to_message_id=callback_query.message.reply_to_message.message_id if callback_query.message.reply_to_message else None
            )
            return await msg.delete()

        # If not in cache, download the track
        artist_title = f'{track.artists} - {track.title}'
        if msg.content_type == types.ContentType.PHOTO:
            print('photo')
            await msg.edit_caption(caption=f"<b>⬇️ Downloading:</b> <code>{artist_title}</code>")
        else:
            print('dalbaeb')
            await msg.edit_text(text=f"<b>⬇️ Downloading:</b> <code>{artist_title}</code>")

        async with YandexMusicSDK() as ym:
            file_path = await ym._download(track.download_info, track.filename)
            
            if not file_path:
                raise FileNotFoundError("Failed to download track")
                
            if msg.content_type == types.ContentType.PHOTO:
                await msg.edit_caption(
                    caption=f"<b>⬆️ Uploading:</b> <code>{artist_title}</code>"
                )
            else:
                await msg.edit_text(
                    text=f"<b>⬆️ Uploading:</b> <code>{artist_title}</code>"
                )
            ym.insert_metadata(track)
            caption = f'{track.caption if hasattr(track, "caption") else artist_title}\n<i>via @yerzhanakh_bot</i>'

            user_track = await bot.send_audio(
                    chat_id=msg.chat.id,
                    audio=types.FSInputFile(file_path),
                    caption=caption,
                    title=track.title,
                    performer=track.artists,
                    duration=int(track.duration),
                    reply_markup=SAVE_BUTTON if callback_query.message.chat.type == 'private' else None,
                    reply_to_message_id=callback_query.message.reply_to_message.message_id if callback_query.message.reply_to_message else None
            )
            cached_track = await bot.copy_message(
                CACHE_CHAT, 
                msg.chat.id,
                user_track.message_id
            )
                
            try:
                db.save_to_cache(cached_track.message_id, track.id)
                logger.info(f'[YandexMusic: track] | Track {track.id} cached successfully')
            except Exception as e:
                    logger.error(f'[YandexMusic: track] | Failed to cache track {track.id} | Error: {e}')
            
            await msg.delete()
            
    except Exception as e:
        error_message = "❌ Error while downloading track"
        logger.error(f'[YandexMusic: track] | {e}\n\n{traceback.print_exc()}')
        await msg.edit_text(error_message)
        
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f'Failed to remove temporary file {file_path}: {e}')


@router.callback_query(F.data.startswith("soundcl_"))
async def download_soundcl_track(callback_query: types.CallbackQuery, bot: Bot):
    track_id = callback_query.data[len("soundcl_"):]  # get track id
    track = cache.get_from_cache("soundcloud", track_id)
    file_path = None

    if not track:
        return await bot.send_message(callback_query.from_user.id, "🚫 Track not found.")
    msg = callback_query.message  # get Message
    try:
        from_chat_id, from_message_id = db.get_cached_media(url=track.track_id)
        
        if from_chat_id and from_message_id:
            await bot.copy_message(
                chat_id=callback_query.message.chat.id,
                from_chat_id=from_chat_id,
                message_id=from_message_id,
                reply_markup=SAVE_BUTTON if callback_query.message.chat.type == 'private' else None,
                reply_to_message_id=callback_query.message.reply_to_message.message_id if callback_query.message.reply_to_message else None
            )
            return await msg.delete()

        # If not in cache, download the track
        artist_title = f'{track.artists} - {track.title}'
        await msg.edit_text(f"<b>⬇️ Downloading:</b> <code>{artist_title}</code>")

        file_path = await sc.save_track(track, 'audio')
            
        if not file_path:
            await msg.edit_text(f"Failed to download track: {artist_title}", reply_markup=CLOSE_BUTTON)
            raise FileNotFoundError("Failed to download track")

        await msg.edit_text(
            f"<b>⬆️ Uploading:</b> <code>{artist_title}</code>"
        )
        caption = f'{track.caption}\n<i>via @yerzhanakh_bot</i>'
            
        user_track = await bot.send_audio(
            chat_id=msg.chat.id,
            audio=types.FSInputFile(file_path),
            caption=caption,
            title=track.title,
            performer=track.artists,
            duration=track.duration,
            reply_markup=SAVE_BUTTON if callback_query.message.chat.type == 'private' else None,
            reply_to_message_id=callback_query.message.reply_to_message.message_id if callback_query.message.reply_to_message else None
        )
        cached_track = await bot.copy_message(
            CACHE_CHAT, 
            msg.chat.id,
            user_track.message_id
        )
                
        try:
            db.save_to_cache(cached_track.message_id, track.link)

            logger.info(f'[Soundcloud: track] | Track {track.link} cached successfully')
        except Exception as e:
            logger.error(f'[Soundcloud: track] | Failed to cache track {track.link} | Error: {e}')
            
        await msg.delete()
            
    except Exception as e:
        error_message = f"❌ Error while downloading track:"
        logger.error(f'[Soundcloud: track] | {str(e)}')
        await msg.edit_text(error_message, parse_mode="HTML", reply_markup=CLOSE_BUTTON)
        
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f'Failed to remove temporary file {file_path}: {e}')