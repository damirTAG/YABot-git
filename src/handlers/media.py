import logging
import os, re
import traceback
import shutil
import pytz
import yt_dlp as ytd
import aiohttp

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
from services.inst          import download_inst_post, download_video

logger  = logging.getLogger()
router  = Router()

tools   = Tools()
db      = DB_actions()

# -- services --
sc = SoundCloudTool()


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
                post_data: metadata = await tt.download(link)
                
                if post_data.type == 'images': # ? images
                    sound = await tt.download_sound(link)
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
                    if media_list and sound:
                        shutil.rmtree(post_data.dir_name)
                        os.remove(sound)
                elif post_data.type == 'video': # ? video
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
                        if video:
                            sended_media = await bot.copy_message(CACHE_CHAT, chat_id, video.message_id)
                            db.save_to_cache(sended_media.message_id, link)
                            os.remove(post_data.media)
                    except exceptions.TelegramNetworkError:
                        await message.reply('Sorry the file is too large')
                        os.remove(post_data.media)
                        logger.error(f'tiktok file too large') 
                    except Exception as e:   
                        logger.exception(f'ERROR DOWNLOADING TIKTOK VIDEO: {e}\nTraceback: {traceback.print_exc()}') 
                    
        except Exception as e:
            logger.exception(f'ERROR DOWNLOADING TIKTOK: {e}\nTraceback: {traceback.print_exc()}')


@router.message(RegexFilter(Patterns.INST_REELS.value))
@log('REELS_LINKS')
async def inst_reels_handler(message: types.Message, bot: Bot):
    event_chat = message.chat

    try:
        logger.info(
            f"(Chat: [ID]: {event_chat.id}, [Title]: {event_chat.title}) (User: [ID]: {message.from_user.id}, [Username]: {message.from_user.username}, [FN]: {message.from_user.first_name}, [SN]: {message.from_user.last_name}) Message: {message.text}")
    except AttributeError:
        pass

    if event_chat.id in IGNORE_CHAT_IDS:
        return False
    else:
        reel_url = await tools.convert_share_urls(message.text)
        await bot.send_chat_action(message.chat.id, 'record_video')

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
        else:
            shortcode = reel_url.split("/")[-1]

            video_filename = f'{shortcode}.mp4'
            url = f'https://ddinstagram.com/videos/{shortcode}/1'

            try:
                await download_video(url, video_filename)

                caption = f'📹 <i>via @yerzhanakh_bot</i>'

                logger.info(f'[Instagram:video] | Sending... [{shortcode}]')

                sended_to_user = await message.answer_video(
                    video=types.FSInputFile(
                        video_filename
                    ), 
                    caption=caption, 
                    reply_to_message_id=message.message_id, 
                    supports_streaming=True,
                    reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None,
                )
                sended_video = await sended_to_user.send_copy(CACHE_CHAT, reply_markup=None)

                db.save_to_cache(sended_video.message_id, reel_url)
            except Exception as e:
                logger.info(f'[Instagram:video] | {e}')
            finally:
                if os.path.exists(video_filename):
                    os.remove(video_filename)

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
        await message.reply("❌ No images found for this post.")
        shutil.rmtree(file_path)
        return

    caption = f'🖼 <i><a href="https://instagram.com/p/{shortcode}">link</a></i>\n\n<i>via @yerzhanakh_bot</i>'

    media_list = []
    for filename in sorted(os.listdir(file_path)):
        file_full_path = os.path.join(file_path, filename)
        if filename.endswith('.mp4'):
            media_list.append(InputMediaVideo(media=open(file_full_path, 'rb'), caption=caption if not media_list else ""))
        elif filename.endswith('.jpg'):
            media_list.append(InputMediaPhoto(media=open(file_full_path, 'rb'), caption=caption if not media_list else ""))

    chunks = [media_list[i:i+10] for i in range(0, len(media_list), 10)]

    if chunks:
        for idx, chunk in enumerate(chunks):
            if idx > 0:
                for item in chunk:
                    item.caption = ""
            await bot.send_media_group(event_chat.id, media=chunk, reply_to_message_id=message.message_id)
    else:
        await message.reply("❌ Failed to retrieve any images.")

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

        cache.add_to_cache("yandexmusic", track.id, track)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬇️ Download", callback_data=f"yandex_{track.id}")],
                [InlineKeyboardButton(text="❌ Close", callback_data="close")]
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
        await bot.send_chat_action(chat_id, 'record_video')
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
                    track = await sc.get_track(link)
                    saved_track = await sc.save_track(track, 'audio')
                except Exception as e:
                    logger.error(f'[soundcloud]: failed to get/save track {e}')
                    chat_id = chat_id
                    await bot.send_message(
                        text=BASE_ERROR, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=CLOSE_BUTTON
                    )

                caption = f'{track.caption}\n<i>via @yerzhanakh_bot</i>'

                try:
                    await bot.send_chat_action(chat_id, 'upload_audio')
                    sended_to_user = await bot.send_audio(
                        chat_id=chat_id, 
                        audio=types.FSInputFile(saved_track),
                        caption=caption,
                        duration=track.duration,
                        performer=track.artists,
                        title=track.title,
                        reply_markup=SAVE_BUTTON if message.chat.type == 'private' else None,
                        reply_to_message_id=message_id
                    )
                    cached_audio = await bot.copy_message(CACHE_CHAT, chat_id, sended_to_user.message_id)
                    try:
                        db.save_to_cache(cached_audio.message_id, link)
                        logger.info(f'[Soundcloud:track] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
                    except Exception as e:
                        logger.info(f'[Soundcloud:track] | Failed to cache {link} | Error: {e}')
                except:
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