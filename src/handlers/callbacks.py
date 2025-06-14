import os, traceback, random

from aiogram                import Router, F, types, Bot

from utils                  import Tools
from config                 import logger
from config.constants       import (
    CACHE_CHAT, SAVE_BUTTON, CLOSE_BUTTON, 
    COOL_PHRASES, SAVE_BUTTON, SAVED, SAVED_BUTTON, ARE_YOU_SURE_STICKER_ID
)
from database.repo          import DB_actions
from database.cache         import cache
from utils.helpers          import build_saved_files_keyboard, build_file_action_keyboard, build_delete_confirmation_keyboard

from services.yandexmusic   import YandexMusicSDK, TrackData
from services.soundcloud    import SoundCloudTool


router  = Router()

db      = DB_actions()

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
            logger.info(f"File {file_type} deleted for user {user_id}")
        else:
            # File does not exist -> save it
            db.save_file(user_id, file_id, file_type)

            await call.answer(
                SAVED.format(file_type.split("/")[0]), True
            )
            await call.message.edit_reply_markup(
                reply_markup=SAVED_BUTTON
            )
            logger.info(f"File {file_type} saved for user {user_id}")

    except Exception as e:
        await call.answer("Failed to process file", show_alert=True)
        logger.error(f"Error handling file {file_type} for user {user_id}: {e}")



@router.callback_query(F.data.startswith("saved_page:"))
async def handle_saved_pagination(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    page = int(callback.data.split(":")[1])
    
    keyboard = build_saved_files_keyboard(user_id, page)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("saved_file:"))
async def handle_saved_file_selection(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    file_db_id = int(callback.data.split(":")[1])

    file_info = db.get_file_by_id(file_db_id)
    
    if not file_info or file_info["user_id"] != user_id:
        await callback.answer("File not found or access denied.")
        return

    file_type = file_info["type"].split('/')[0].lower()
    file_id = file_info["file_id"]
    action_keyboard = build_file_action_keyboard(file_db_id)
    
    try:
        await callback.message.delete()
        if file_type == "video":
            await callback.message.answer_video(
                video=file_id,
                caption="Your saved video",
                reply_markup=action_keyboard
            )
        elif file_type == "audio":
            await callback.message.answer_audio(
                audio=file_id,
                caption="Your saved audio",
                reply_markup=action_keyboard
            )
        else:
            await callback.message.reply(
                f"Unknown file type: {file_type}",
                reply_markup=action_keyboard
            )
            
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error sending saved file: {e}")
        await callback.answer("Failed to send the file. It may have been deleted from Telegram servers.")

# Handle delete file callback
@router.callback_query(F.data.startswith("delete_file:"))
async def handle_delete_file_request(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    file_db_id = int(callback.data.split(":")[1])
    
    file_info = db.get_file_by_id(file_db_id)
    
    if not file_info or file_info["user_id"] != user_id:
        await callback.answer("File not found or access denied.")
        return

    file_type = file_info["type"].split('/')[0].lower()

    confirmation_keyboard = build_delete_confirmation_keyboard(file_db_id)
    
    await callback.message.answer_sticker(ARE_YOU_SURE_STICKER_ID)

    await callback.message.reply(
        f"Are you sure you want to delete this {file_type}?",
        reply_markup=confirmation_keyboard
    )
    
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete:"))
async def handle_delete_confirmation(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    file_db_id = int(callback.data.split(":")[1])

    file_info = db.get_file_by_id(file_db_id)
    
    if not file_info or file_info["user_id"] != user_id:
        await callback.answer("File not found or access denied.")
        return

    delete_query = """
        DELETE FROM user_saved
        WHERE id = ?
    """
    
    success = db.execute_query(delete_query, (file_db_id,))
    
    if success:
        await callback.answer("File deleted successfully.")
        
        # Get updated file count
        query = """
            SELECT COUNT(*) FROM user_saved
            WHERE user_id = ?
        """
        result = db.execute_query(query, (user_id,), fetch_all=False)
        total_files = result[0] if result else 0
        
        if total_files == 0:
            try:
                await callback.message.delete()
                await callback.message.answer("You have no saved files yet.")
            except Exception as e:
                logger.error(f"Error updating file list: {e}")
        else:
            keyboard = build_saved_files_keyboard(user_id)
            
            try:
                await callback.message.delete()
                await callback.message.answer(
                    f"You have {total_files} saved {'file' if total_files == 1 else 'files'}. "
                    f"Select one to view:",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error updating file list: {e}")
    else:
        await callback.answer("Failed to delete the file.")


# Handle back to files list callback
@router.callback_query(F.data == "back_to_files")
async def handle_back_to_files(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    query = """
        SELECT COUNT(*) FROM user_saved
        WHERE user_id = ?
    """
    result = db.execute_query(query, (user_id,), fetch_all=False)
    total_files = result[0] if result else 0
    
    if total_files == 0:
        await callback.message.edit_text("You have no saved files.")
    else:
        keyboard = build_saved_files_keyboard(user_id)

        await callback.message.delete()
        return await callback.message.answer(
            f"You have {total_files} saved {'file' if total_files == 1 else 'files'}. "
            f"Select one to view:",
            reply_markup=keyboard
        )
    
    await callback.answer()

# -- platforms callbacks -- 

@router.callback_query(F.data.startswith("yandex_"))
async def download_yandex_track(callback_query: types.CallbackQuery, bot: Bot):
    track_id = int(callback_query.data.removeprefix("yandex_"))
    track = cache.get_from_cache("yandexmusic", int(track_id))
    file_path = None

    if not track:
        return await bot.send_message(callback_query.from_user.id, "🚫 Track not found.")
    msg = callback_query.message  # get Message
    try:
        results = db.get_cached_media(url=track.id)
        
        if results:
            from_chat_id, from_message_id = results
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
    track_id = callback_query.data.removeprefix("soundcl_")  # get track id
    track = cache.get_from_cache("soundcloud", track_id)
    file_path = None

    if not track:
        return await bot.send_message(callback_query.from_user.id, "🚫 Track not found.")
    msg = callback_query.message  # get Message
    try:
        results = db.get_cached_media(url=track.track_id)
        
        if results:
            from_chat_id, from_message_id = results
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