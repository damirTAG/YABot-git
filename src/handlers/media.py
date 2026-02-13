import logging
import os, re
import traceback
import shutil
import pytz
import yt_dlp as ytd
import aiohttp
import asyncio

from datetime           import datetime

from aiogram            import Router, F, types, Bot, exceptions
from aiogram.types      import InputMediaPhoto, InputMediaVideo, InlineKeyboardMarkup, InlineKeyboardButton

from utils              import Tools, RegexFilter, ConsoleColors, YANDEX_MUSIC_TRACK_CAPTION
from utils.decorators   import log
from config.constants   import (
    CACHE_CHAT, 
    SAVE_BUTTON, 
    CLOSE_BUTTON,
    BASE_ERROR,
    IGNORE_CHAT_IDS
)
from config.enums       import Patterns
from database.repo      import DB_actions
from database.cache     import cache

from services.yandexmusic   import YandexMusicSDK, TrackData
from services.soundcloud    import SoundCloudTool
from services.tiktok        import TikTok, metadata
from services.inst          import download_inst_post, download_instagram_reel
from services.youtube       import YouTubeSDK

logger  = logging.getLogger()
router  = Router()

tools   = Tools()
db      = DB_actions()

# -- services --
sc = SoundCloudTool()
youtube = YouTubeSDK(
    output_dir="yt_video",
    quality="720p",
)


# -- brainrot platforms first --

@router.message(RegexFilter(Patterns.TIKTOK.value))
@log('TIKTOK_LINKS')
async def tiktok_downloader(message: types.Message, bot: Bot):
    if message.chat.id in IGNORE_CHAT_IDS:
        return False
    else:
        await bot.send_chat_action(message.chat.id, 'record_video')
        event_chat = message.chat
        chat_id = message.chat.id
        match = re.search(Patterns.TIKTOK.value, message.text)
        if match:
            link: str = match.group(0)

        try:
            logger.info(
                f"(Chat: [ID]: {event_chat.id}, [Title]: {event_chat.title}) "
                f"[Username]: {message.from_user.username}, "
                f"Link: {link}")
        except AttributeError:
            pass
        
        try:
            async with TikTok() as tt:
                cache_result = db.get_cached_media(link)
                if cache_result:
                    from_chat_id, from_message_id = cache_result
                    return await bot.copy_message(
                        message.chat.id, 
                        from_chat_id, 
                        from_message_id, 
                        reply_to_message_id=message.message_id,
                        reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None
                    )
                
                await tt._ensure_data(link)
                
                post_data, sound = await asyncio.gather(
                    tt.download(link),
                    tt.download_sound(link)
                )
                
                if post_data.type == 'images': # ? images
                    media_list = []
                    for img in post_data.media:
                        media_list.append(InputMediaPhoto(media=types.FSInputFile(img)))

                    chunks = [media_list[i:i+10] for i in range(0, len(media_list), 10)]
                    if chunks:
                        for chunk in chunks:
                            await bot.send_media_group(
                                event_chat.id, 
                                media=chunk, 
                                reply_to_message_id=message.message_id
                            )
                        try:
                            await bot.send_audio(
                                chat_id=chat_id, 
                                audio=types.FSInputFile(sound), 
                                reply_to_message_id=message.message_id,
                                reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None,
                                title=str(sound.split('.')[0])
                            )
                        except Exception as e:
                            logger.info(f"Error with sound sending: {e}")
                    else:
                        await message.reply("❌ Failed to retrieve any images.")
                    if media_list:
                        shutil.rmtree(post_data.dir_name)
                    if sound:
                        os.remove(sound)
                        
                elif post_data.type == 'video':
                    try:
                        caption = '<i>via @yerzhanakh_bot</i>'

                        video = await bot.send_video(
                            chat_id=chat_id,
                            caption=caption,
                            reply_to_message_id=message.message_id,
                            video=types.FSInputFile(post_data.media),
                            supports_streaming=True,
                            duration=post_data.duration,
                            width=post_data.width,
                            height=post_data.height,
                            reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None
                        )

                        try:
                            if db.get_setting(chat_id, "tiktok_send_sound_videos_disabled"):
                                return

                            await bot.send_audio(
                                chat_id=chat_id,
                                audio=types.FSInputFile(sound),
                                reply_to_message_id=message.message_id,
                                reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None,
                                title=str(sound.split('.')[0])
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send sound: {e}")

                        if video:
                            cached_video = await bot.copy_message(CACHE_CHAT, chat_id, video.message_id)
                            db.save_to_cache(cached_video.message_id, link)

                        os.remove(post_data.media)
                        os.remove(sound)

                    except exceptions.TelegramNetworkError:
                        await message.reply('Sorry, the file is too large.')
                        logger.error(f'TikTok file too large: {link}')
                        for f in (post_data.media, sound):
                            if os.path.exists(f):
                                os.remove(f)

                    except Exception as e:
                        logger.exception(f'ERROR DOWNLOADING TIKTOK VIDEO: {e}\nTraceback: {traceback.print_exc()}')
                        for f in (post_data.media, sound):
                            if os.path.exists(f):
                                os.remove(f)

                    
        except Exception as e:
            logger.exception(f'ERROR DOWNLOADING TIKTOK: {e}\nTraceback: {traceback.print_exc()}')


@router.message(RegexFilter(Patterns.INST_REELS.value))
@log('REELS_LINKS')
async def inst_reels_handler(message: types.Message, bot: Bot):
    event_chat = message.chat

    try:
        logger.info(
            f"(Chat: [ID]: {event_chat.id}, [Title]: {event_chat.title}) "
            f"(User: [ID]: {message.from_user.id}, [Username]: {message.from_user.username}, "
            f"[FN]: {message.from_user.first_name}, [SN]: {message.from_user.last_name}) "
            f"Message: {message.text}"
        )
    except AttributeError:
        pass

    if event_chat.id in IGNORE_CHAT_IDS:
        return False
    
    reel_url = await tools.convert_share_urls(message.text)
    await bot.send_chat_action(message.chat.id, 'record_video')

    # Check cache first
    result = db.get_cached_media(reel_url)
    if result:
        from_chat_id, from_message_id = result
        return await bot.copy_message(
            event_chat.id, 
            from_chat_id, 
            from_message_id, 
            reply_to_message_id=message.message_id,
            reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None
        )
    
    # Extract shortcode for filename
    shortcode = reel_url.rstrip('/').split("/")[-1]
    download_dir = './temp_downloads'
    os.makedirs(download_dir, exist_ok=True)
    
    video_filename = os.path.join(download_dir, f'{shortcode}.mp4')

    try:
        # Use yt-dlp to download the reel
        logger.info(f'[Instagram:reel] | Downloading... [{shortcode}]')
        success = await download_instagram_reel(
            url=reel_url,
            download_dir=download_dir,
            filename=shortcode
        )
        
        if not success:
            await message.reply("❌ Failed to download reel. Please try again later.")
            return

        # Check if file was downloaded
        if not os.path.exists(video_filename):
            # yt-dlp might have used a different extension, search for the file
            possible_files = [f for f in os.listdir(download_dir) if f.startswith(shortcode)]
            if possible_files:
                video_filename = os.path.join(download_dir, possible_files[0])
            else:
                await message.reply("❌ Downloaded file not found.")
                return

        caption = f'📹 <i>via @yerzhanakh_bot</i>'

        logger.info(f'[Instagram:reel] | Sending... [{shortcode}]')

        # Send to user
        sended_to_user = await message.answer_video(
            video=types.FSInputFile(video_filename), 
            caption=caption, 
            reply_to_message_id=message.message_id, 
            supports_streaming=True,
            reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None,
        )
        
        sended_video = await sended_to_user.send_copy(CACHE_CHAT, reply_markup=None)

        db.save_to_cache(sended_video.message_id, reel_url)
        
        logger.info(f'[Instagram:reel] | Successfully sent [{shortcode}]')

    except Exception as e:
        logger.exception(f'[Instagram:reel] | Error processing {shortcode}: {e}')
        await message.reply("❌ An error occurred while processing the reel.")
    finally:
        if os.path.exists(video_filename):
            os.remove(video_filename)
            logger.info(f'[Instagram:reel] | Cleaned up {video_filename}')
        
        try:
            if os.path.exists(download_dir) and not os.listdir(download_dir):
                os.rmdir(download_dir)
        except Exception:
            pass

@router.message(RegexFilter(Patterns.INST_POSTS.value))
@log('INST_POST')
async def inst_photos_handler(message: types.Message, bot: Bot):
    event_chat = message.chat
    if event_chat.id in IGNORE_CHAT_IDS:
        return False

    try:
        logger.info(
            f"(Chat: [ID]: {event_chat.id}, [Title]: {event_chat.title}) (User: [ID]: {message.from_user.id}, "
            f"[Username]: {message.from_user.username}, [FN]: {message.from_user.first_name}, [SN]: {message.from_user.last_name}) "
            f"Message: {message.text}"
        )
    except AttributeError:
        pass

    await bot.send_chat_action(message.chat.id, 'upload_photo')
    post_url = message.text
    shortcode = post_url.split("/")[-2]

    urls_to_check: list = [f'https://ddinstagram.com/images/{shortcode}/{i}' for i in range(1, 21)]

    file_path = f'{shortcode}'
    os.makedirs(file_path, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        valid_images = []
        for url in urls_to_check:
            success = await download_inst_post(session, url, file_path)
            if success:
                valid_images.append(url)
                logger.info('success')
            else:
                logger.info('no success')
                break  # Stop checking after first 404

    if not valid_images:
        await message.reply("❌ Failed to get content from this post.", reply_markup=CLOSE_BUTTON)
        shutil.rmtree(file_path)
        return

    caption = f'🖼 <i><a href="https://instagram.com/p/{shortcode}">link</a></i>\n\n<i>via @yerzhanakh_bot</i>'

    media_list = []
    for filename in sorted(os.listdir(file_path)):
        file_full_path = os.path.join(file_path, filename)
        if filename.endswith('.mp4'):
            media_list.append(
                InputMediaVideo(
                    media=types.FSInputFile(file_full_path), caption=caption if not media_list else None
                )
            )
        elif filename.endswith('.jpg'):
            media_list.append(
                InputMediaPhoto(
                    media=types.FSInputFile(file_full_path), caption=caption if not media_list else None
                )
            )

    chunks = [media_list[i:i+10] for i in range(0, len(media_list), 10)]

    if chunks:
        for idx, chunk in enumerate(chunks):
            if idx > 0:
                for item in chunk:
                    item.caption = ""
            await bot.send_media_group(event_chat.id, media=chunk, reply_to_message_id=message.message_id)
    else:
        await message.reply("❌ Failed to retrieve any images.", reply_markup=CLOSE_BUTTON)

    shutil.rmtree(file_path)
    logger.info(f"[Instagram:post] | {shortcode} folder removed successfully")


@router.message(RegexFilter(Patterns.TWITCH_VK.value))
@log('TWITCH_VK_LINKS')
async def twitch_vk_handler(message: types.Message, bot: Bot):
    event_chat = message.chat
    message_id = message.message_id
    try:
        logger.info(
            f"(Chat: [ID]: {event_chat.id}, [Title]: {event_chat.title}) (User: [ID]: {message.from_user.id}, "
            f"[Username]: {message.from_user.username}, [FN]: {message.from_user.first_name}, [SN]: {message.from_user.last_name}) "
            f"Message: {message.text}"
        )
    except AttributeError:
        pass
    link = message.text

    await bot.send_chat_action(message.chat.id, 'record_video')
    
    cache_result = db.get_cached_media(link)
    if cache_result:
        from_chat_id, from_message_id = cache_result
        await bot.copy_message(
            message.chat.id, 
            from_chat_id, 
            from_message_id, 
            reply_to_message_id=message_id,
            reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None
        )
    else:
        options = {
            'skip-download': True,
            'format': 'mp4',
            'outtmpl': 'video/%(id)s.%(ext)s',
            'cookies-from-browser': 'chrome',
            'cookies': 'cookies.txt',
            'noplaylist': True,
        }
        try:
            with ytd.YoutubeDL(options) as ytdl:
                logger.info('Downloading VK | Twitch')
                result = ytdl.extract_info("{}".format(link))
                title = ytdl.prepare_filename(result)
                ytdl.download([link])
        except:
            await bot.send_message(
                text=BASE_ERROR, 
                chat_id=message.chat.id, 
                reply_to_message_id=message_id, 
                reply_markup=CLOSE_BUTTON
            )
                
        video_title = result.get('title', None)
        uploader = result.get('uploader', None)
        video = open(f'{title}', 'rb')
        caption = f"📹: <a href='{link}'>{video_title}</a>\n\n👤: <a href='{link}'>{uploader}</a>"
        try:
            sended_to_user = await bot.send_video(
                chat_id=message.chat.id, 
                video=types.FSInputFile(video), 
                caption=caption, 
                reply_to_message_id=message.message_id, 
                supports_streaming=True,
                reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None
            )
            sended_media = await bot.copy_message(CACHE_CHAT, message.chat.id, sended_to_user.message_id)
            try:
                if db.get_cached_media(sended_media.message_id, link):
                    logger.info(f'[Media:video] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
                else:
                    logger.info(f'[Media:video] | {ConsoleColors.FAIL}{link} Failed to cache{ConsoleColors.ENDC}')
            except Exception as e:
                logger.info(f'[Media:video] | Failed to cache {link}')
        except:
            await bot.send_message(
                text=BASE_ERROR, 
                chat_id=message.chat.id, 
                reply_to_message_id=message_id, 
                reply_markup=CLOSE_BUTTON
            )
        finally:
            if os.path.exists(title):
                os.remove(title)
                logger.info("%s has been removed successfuly" % title)

@router.message(RegexFilter(Patterns.YOUTUBE.value))
@log('YOUTUBE_VIDEO')
async def handle_youtube_video(m: types.Message, bot: Bot):
    if m.chat.id in IGNORE_CHAT_IDS:
        return False
    await bot.send_chat_action(m.chat.id, 'record_video')

    match = re.search(Patterns.YOUTUBE.value, m.text)
    if match:
        link: str = match.group(0)

    try:
        logger.info(
            f"(Chat: [ID]: {m.chat.id}, [Title]: {m.chat.title}) "
            f"[Username]: {m.from_user.username}, "
            f"Link: {link}"
        )
    except AttributeError:
        pass

    ready_youtube_obj = None

    try:
        cache_result = db.get_cached_media(link)
        if cache_result:
            from_chat_id, from_message_id = cache_result
            return await bot.copy_message(
                m.chat.id,
                from_chat_id,
                from_message_id,
                reply_to_message_id=m.message_id,
                reply_markup=SAVE_BUTTON if m.chat.type == 'private' else None
            )

        ready_youtube_obj = await youtube.download(link)

        if ready_youtube_obj:
            try:
                video = await bot.send_video(
                    chat_id=m.chat.id,
                    caption='<i>via @yerzhanakh_bot</i>',
                    reply_to_message_id=m.message_id,
                    video=types.FSInputFile(ready_youtube_obj),
                    supports_streaming=True,
                    reply_markup=SAVE_BUTTON if m.chat.type == 'private' else None
                )
                if video:
                    sended_media = await bot.copy_message(CACHE_CHAT, m.chat.id, video.message_id)
                    db.save_to_cache(sended_media.message_id, link)
            except exceptions.TelegramNetworkError:
                await m.reply('Sorry, the file is too large')
                logger.error('Youtube video file is too large')
            except Exception as e:
                logger.exception(
                    f'ERROR DOWNLOADING YOUTUBE VIDEO: {e}\nTraceback: {traceback.format_exc()}'
                )
        else:
            await m.reply('Sorry, the video exceeds duration limit (6 min)')

    except Exception as e:
        logger.error(f'Error in handle_youtube_video: {e}')

    finally:
        try:
            if ready_youtube_obj and os.path.exists(ready_youtube_obj):
                os.remove(ready_youtube_obj)
        except Exception as cleanup_err:
            logger.warning(f"Cleanup failed: {cleanup_err}")

# -- music platforms link handlers --

@router.message(RegexFilter(Patterns.YANDEX_MUSIC.value))
@log('YM_TRACK_LINKS')
async def yandex_music_link_handler(m: types.Message):
    match = re.search(Patterns.YANDEX_MUSIC.value, m.text)
    if match:
        track_link = match.group(0)
    
    async with YandexMusicSDK() as ym:
        track: TrackData = await ym.get_track(track_link)
        if not track:
            return await m.answer("🚫 Track not found =000")        

        cache.add_to_cache("yandexmusic", int(track.id), track)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬇️ Download", callback_data=f"yandex_{track.id}", style="primary")],
                [InlineKeyboardButton(text="❌ Close", callback_data="close", style="danger")]
            ]
        )
        
        caption = YANDEX_MUSIC_TRACK_CAPTION(track).format()
        await m.answer_photo(
            photo=types.URLInputFile(track.cover),
            caption=caption,
            reply_to_message_id=m.message_id,
            reply_markup=keyboard
        )

@router.message(RegexFilter(Patterns.SOUNDCLOUD.value))
@log('SC_TRACK_LINKS')
async def soundload(message: types.Message, bot: Bot):
    chat_id = message.chat.id
    message_id = message.message_id
    if chat_id in IGNORE_CHAT_IDS:
        return False
    else:
        await bot.send_chat_action(chat_id, 'record_voice')
        match = re.search(Patterns.SOUNDCLOUD.value, message.text)
        if match:
            link = match.group(0)
            if link and 'https://on.' in link:
                link = await tools.convert_share_urls(link)
            current_date = datetime.now(pytz.timezone('Asia/Almaty'))
            if current_date.tzinfo == None or current_date.\
                    tzinfo.utcoffset(current_date) == None:
                logger.info("Unaware")
            else:
                logger.info("======")
            username = message.from_user.full_name
            logger.info(f"[{current_date}] {username} : {link}")

            # Check cache first
            result = db.get_cached_media(link)
            if result:
                from_chat_id, from_message_id = result
                return await bot.copy_message(
                    chat_id, from_chat_id, from_message_id, reply_to_message_id=message_id,
                    reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None,
                )
            else:
                logger.info("downloading mp3 format | SOUNDCLOUD")
                try:
                    track = await sc.get_track(str(link))
                    saved_track = await sc.save_track(track, 'audio')
                except Exception as e:
                    logger.error(f'[soundcloud]: failed to get/save track {e}')
                    chat_id = chat_id
                    await bot.send_message(
                        text=BASE_ERROR, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=CLOSE_BUTTON
                    )

                caption = f'{track.caption}\n<i>via @yerzhanakh_bot</i>'

                try:
                    await bot.send_chat_action(chat_id, 'upload_voice')
                    sended_to_user = await message.reply_audio(
                        audio=types.FSInputFile(saved_track),
                        caption=caption,
                        duration=int(track.duration),
                        performer=track.artists,
                        title=track.title,
                        reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None
                    )
                    cached_audio = await bot.copy_message(CACHE_CHAT, chat_id, sended_to_user.message_id)
                    try:
                        db.save_to_cache(cached_audio.message_id, link)
                        logger.info(f'[Soundcloud:track] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
                    except Exception as e:
                        logger.info(f'[Soundcloud:track] | Failed to cache {link} | Error: {e}')
                except Exception as e:
                    logger.error(f'Failed to send soundcloud track: {e}')
                    return await bot.send_message(
                        text=BASE_ERROR, 
                        chat_id=chat_id, 
                        reply_to_message_id=message_id, 
                        reply_markup=CLOSE_BUTTON
                    )
                finally:
                    # deleting file after
                    if saved_track:
                        os.remove(saved_track)
                        logger.info("%s has been removed successfuly" % saved_track)
        else:
            logger.info(f'[soundcloud]: link not found, message: {message.text}')       