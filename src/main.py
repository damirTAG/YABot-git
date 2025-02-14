# INIT START
from config import TOKEN

# TEXT FILES IMPORT BEGIN
from allText import start_txt, text_txt, error_txt, help_txt, update_txt
# TEXT FILES IMPORT END

import pytz
import yt_dlp as ytd
import os, re, uuid
import sqlite3
import json
import aiohttp
import shutil
import logging
import traceback


from modules import (
    Tools, 
    ConsoleColors,
    SoundCloudTool,
    Platforms,
    TikTok, 
    metadata,
    Converter
)
from exceptions import SoundCloudSearchException


from mutagen.id3 import ID3, TIT2, TPE1
from random import randrange
from tinytag import TinyTag
from datetime import datetime
from urllib.parse import urlparse, unquote
from tqdm.asyncio import tqdm


from aiogram.utils.exceptions import ChatNotFound
from aiogram.dispatcher import FSMContext
from aiogram.utils.exceptions import Unauthorized, BotBlocked, ChatNotFound
from aiogram.dispatcher.filters import Text
from aiogram import Dispatcher, Bot, executor, types
from aiogram import asyncio
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatActions, InputMediaPhoto, InputMediaVideo, ChatType, InlineQuery, InputTextMessageContent, InlineQueryResultArticle
# =========
storage = MemoryStorage()
semaphore = asyncio.Semaphore(20)
#BOT INIT
bot = Bot(TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=storage)
tools = Tools()
#DATABASE
conn = sqlite3.connect('audio_cache.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS audio_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        message_id INTEGER,
        audio_link TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS video_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        message_id INTEGER,
        video_link TEXT
    )
''')
#LOGER
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = logging.FileHandler('bot.log', encoding='UTF-8')
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
#
DAMIR_USER_ID = 1038468423
GITHUB_REPO = 'None'
CACHE_CHAT = -1001911592881
pl = Platforms()
ignore_ids = [-1001559555304, -1001919227306, -1001987624296, -1002050266275]   # -1001559555304, -1001919227306, -1001987624296

# ERRORS
async def on_unauthorized_error(update: types.Update, exception: Exception):
    if isinstance(exception, BotBlocked):
        logger.info(f'User has blocked the bot, skipping')

# =========
# INIT FINISH

async def get_user_info(user_id):
    try:
        user = await bot.get_chat(user_id)
        username = user.username
        fullname = user.full_name
        return username, fullname
    except ChatNotFound:
        logger.info('chat not found skipping...')
        return None, None

@dp.message_handler(commands='start')
async def hello(message: types.Message):
    await message.reply(text=start_txt)



def get_last_active_users():
    query = """
    SELECT user_id, MAX(timestamp) 
    FROM user_activity 
    """
    cursor.execute(query)
    return cursor.fetchall()


def get_my_chats():
    query = """
    SELECT chat_id, chat_name
    FROM chats 
    """
    cursor.execute(query)
    return cursor.fetchall()

almaty_tz = pytz.timezone('Etc/GMT-5')

@dp.callback_query_handler(text="close")
async def close(call: types.CallbackQuery):
    await bot.delete_message(call.message.chat.id, call.message.message_id)

@dp.message_handler(commands=['admin'])
async def send_data(message: types.Message):
    if message.from_user.id == 1038468423:
        active_users = get_last_active_users()
        chats = get_my_chats()
        
        response = "Chat data:\n"
        
        for chat_id, chat_name in chats:
            response += f"Chat ID: {chat_id}, Name: {chat_name}\n"
        
        response += "\nLast Active Users not in any chats:\n"
        
        for user_id, timestamp in active_users:
            timestamp = datetime.fromisoformat(timestamp).replace(tzinfo=pytz.utc).astimezone(almaty_tz)
            response += f"User ID: {user_id}, Last Active: {timestamp}\n"
        
        await message.reply(response)

@dp.message_handler(commands=['sendall'])
async def send_all(message: types.Message):
    if message.from_user.id == 1038468423:
        try:
            with open('user_ids.json', 'r') as file:
                user_ids = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            user_ids = []

        for user_id in user_ids:
            await bot.send_message(chat_id=user_id, text=update_txt)
    else:
        return False


@dp.message_handler(commands='help', commands_prefix='!/')
async def help(message: types.Message):
    help = help_txt
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(text='Dev 🧑‍💻', url='https://t.me/DAMIRTAG'),
    )
    await message.reply(text=help, reply_markup=keyboard)

# roll
@dp.message_handler(commands=['roll', 'ролл'], commands_prefix='!/.')
async def rate(message: types.Message):
    nick = message.from_user.first_name
    chat_id = message.chat.id
    random = (randrange(101))
    roll = f'🎱 <b>{nick}</b> роллит! [1-100]. Выпадает: <b>{random}</b>!'
    return await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=roll)

from modules.ymtool import YandexMusicSDK, TrackData

ya_track_data: dict = {}
YANDEX_MUSIC_PATTERN = r"https://music\.yandex\.(?:ru|com|kz)/album/\d+/track/\d+"

@dp.message_handler(commands=['ym'])
async def ym_command_handler(message: types.Message):
    args: str = message.get_args()
    if not args:
        return await message.reply("❌ Укажите поисковый запрос. Пример: <code>/ym The Beatles</code>")

    search_msg = await message.reply(f"<b>🔍 Searching:</b> <code>{args}</code>")
    async with YandexMusicSDK() as ym:
        results: list[TrackData] = await ym.search(args, count=10, download=False)
        if not results:
            return await search_msg.edit_text("🚫 Tracks not found =000")

        keyboard = InlineKeyboardMarkup()
        for track in results:
            track_uuid = uuid.uuid4().hex[:8]
            ya_track_data[track_uuid] = track
            
            keyboard.add(
                InlineKeyboardButton(
                    f"{track.artists} - {track.title}", 
                    callback_data=f"yandex_{track_uuid}"
                )
            )
        keyboard.add(
            InlineKeyboardButton(
                text='❌ Close',
                callback_data='close'
            ),
        )
        await search_msg.delete()
        await message.reply(f'<b>{args.capitalize()}</b>', reply_markup=keyboard)

@dp.message_handler(regexp=YANDEX_MUSIC_PATTERN)
async def yandex_music_link_handler(m: types.Message):
    match = re.search(YANDEX_MUSIC_PATTERN, m.text)
    if match:
        track_link = match.group(0)
    
    async with YandexMusicSDK() as ym:
        track: TrackData = await ym.get_track(track_link)
        if not track:
            return await m.answer("🚫 Track not found =000")        

        track_uuid = uuid.uuid4().hex[:8]
        ya_track_data[track_uuid] = track

        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("⬇️ Download", callback_data=f"yandex_{track_uuid}"),
            InlineKeyboardButton("❌ Close", callback_data='close')
        )
        
        caption = f"""
<b>🎵 Track:</b> <a href='https://music.yandex.com/album/{track.album_id}/track/{track.id}'>{track.title}</a> • {track.year}
<b>👥 Artists:</b> <i>{track.artists}</i>
<b>📀 Album:</b> <a href='https://music.yandex.com/album/{track.album_id}'>{track.album_title}</a>
<b>🎶 Genre:</b> <i>{track.genre.capitalize()}</i>
<b>⏱️ Duration:</b> <code>{int(track.duration // 60)}:{int(track.duration % 60):02d}</code>
"""
        await bot.send_photo(
            m.chat.id,
            track.cover,
            caption,
            reply_to_message_id=m.message_id,
            reply_markup=keyboard
        )
        # ya_track_data["msg_id"] = msg.message_id

@dp.callback_query_handler(lambda c: c.data.startswith("yandex_"))
async def download_yandex_track(callback_query: types.CallbackQuery):
    # await callback_query.answer()
    track_uuid = callback_query.data[len("yandex_"):]  # get UUID
    file_path = None

    if track_uuid not in ya_track_data:
        return await bot.send_message(callback_query.from_user.id, "🚫 Track not found.")

    track: TrackData = ya_track_data[track_uuid]  # get  TrackData  obj
    msg = callback_query.message  # get Message
    try:
        # Check cache first
        cursor.execute('SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (track.id,))
        result = cursor.fetchone()
        
        if result:
            from_chat_id, from_message_id = result
            await bot.copy_message(
                chat_id=callback_query.message.chat.id,
                from_chat_id=from_chat_id,
                message_id=from_message_id,
                reply_to_message_id=callback_query.message.reply_to_message.message_id if callback_query.message.reply_to_message else None
            )
            await msg.delete()
            return

        # If not in cache, download the track
        artist_title = f'{track.artists} - {track.title}'
        if msg.content_type == types.ContentType.PHOTO:
            await msg.edit_caption(f"<b>⬇️ Downloading:</b> <code>{artist_title}</code>")
        else:
            await msg.edit_text(f"<b>⬇️ Downloading:</b> <code>{artist_title}</code>")

        async with YandexMusicSDK() as ym:
            file_path = await ym._download(track.download_info, track.filename)
            
            if not file_path:
                raise FileNotFoundError("Failed to download track")
                
            if msg.content_type == types.ContentType.PHOTO:
                await msg.edit_caption(
                    f"<b>⬆️ Uploading:</b> <code>{artist_title}</code>"
                )
            else:
                await msg.edit_text(
                    f"<b>⬆️ Uploading:</b> <code>{artist_title}</code>"
                )
            ym.insert_metadata(track)
            caption = f'{track.caption if hasattr(track, "caption") else artist_title}\n<i>via @yerzhanakh_bot</i>'
            
            with open(file_path, "rb") as audio:
                user_track = await bot.send_audio(
                    chat_id=msg.chat.id,
                    audio=audio,
                    caption=caption,
                    title=track.title,
                    performer=track.artists,
                    reply_to_message_id=callback_query.message.reply_to_message.message_id if callback_query.message.reply_to_message else None
                )
                cached_track = await bot.copy_message(
                    CACHE_CHAT, 
                    msg.chat.id,
                    user_track.message_id
                )
                
                try:
                    cursor.execute(
                        'INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                        (CACHE_CHAT, cached_track.message_id, track.id)
                    )
                    conn.commit()
                    logger.info(f'[YandexMusic: track] | Track {track.id} cached successfully')
                except Exception as e:
                    logger.error(f'[YandexMusic: track] | Failed to cache track {track.id} | Error: {e}')
            
            await msg.delete()
            
    except Exception as e:
        error_message = f"❌ Error while downloading track:"
        logger.error(f'[YandexMusic: track] | {str(e)}')
        await msg.edit_text(error_message, parse_mode="HTML")
        
    finally:
        if track_uuid in ya_track_data:
            del ya_track_data[track_uuid]
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f'Failed to remove temporary file {file_path}: {e}')


# speech rec


@dp.message_handler(content_types=['voice', 'video_note'])
async def get_audio_messages(message: types.Message):
    try:
        await bot.send_chat_action(message.chat.id, ChatActions.TYPING)
        file_id = message.voice.file_id if message.content_type in [
            'voice'] else message.video_note.file_id
        file_info = await bot.get_file(file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        file_name = str(message.message_id) + '.ogg'
        name = message.chat.first_name if message.chat.first_name else 'No_name'
        logger.info(
            f"Chat {name} (ID: {message.chat.id}) download file {file_name}")

        with open(file_name, 'wb') as new_file:
            new_file.write(downloaded_file.getvalue())
        converter = Converter(file_name)
        os.remove(file_name)
        message_text = f"<i><b>{converter.audio_to_text()}</b></i>"
        del converter
        await bot.send_message(message.chat.id, text=message_text,
                               reply_to_message_id=message.message_id)
    except:
        return False

# video download


@dp.callback_query_handler(text='download_mp4')
async def inline_keyboard_mp4(call: types.CallbackQuery):
    logger.info("downloading mp4 format")
    loading = "<i>Жүктеу | Loading</i>"
    await call.message.edit_text(text=loading)
    chat_id = call.message.chat.id
    # database = Database('database/users.db')

    cursor.execute(
                'SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (link,))
    cache_result = cursor.fetchone()
    if cache_result:
            from_chat_id, from_message_id = cache_result
            await bot.copy_message(chat_id, from_chat_id, from_message_id, reply_to_message_id=message_id)
            await bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        options = {
            'skip-download': True,
            'noplaylist': True,
            'format': 'mp4',
        }

        with ytd.YoutubeDL(options) as ytdl:
            result = ytdl.extract_info("{}".format(link), download=False)
            duration = result['duration']
            try:
                if duration and duration <= 360:
                    url = result['url']
                    video_id = result['id']

                    # Metadata
                    # title = ytdl.prepare_filename(result)
                    video_title = result.get('title', None)
                    channel = result.get('uploader_id', None)
                    uploader = result.get('uploader', None)


                    uploader_link = f'https://www.youtube.com/{channel}'
                    delete = (f'yt/{video_id}.mp4')
                    try:
                        async with aiohttp.ClientSession() as session:
                                async with session.get(url) as response:
                                    if response.status == 200:
                                        logger.info(response.status)
                                        total_size = int(response.headers.get('content-length', 0))
                                        with open(delete, 'wb') as f, tqdm(
                                            total=total_size, unit='B', unit_scale=True, desc=delete) as pbar:
                                            async for chunk in response.content.iter_any():
                                                f.write(chunk)
                                                pbar.update(len(chunk))
                                        logger.info(f"[Youtube:video] | Downloaded and saved as {delete}")
                                    else:
                                        logger.info(f"[Youtube:video] | Can't get data from {url}| Response: {response.status}")
                    except Exception as e:
                        logger.info(e)
                        keyboard = InlineKeyboardMarkup()
                        keyboard.add(
                            InlineKeyboardButton(
                                text='❌ Close',
                                callback_data='close'
                            ),
                        )
                        await bot.delete_message(call.message.chat.id, call.message.message_id)
                        await bot.send_message(text=error_txt, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
                
                    caption = f"📹: <a href='{link}'>{video_title}</a>\n\n👤: <a href='{uploader_link}'>{uploader}</a>"
                    await bot.delete_message(call.message.chat.id, call.message.message_id)
                    await bot.send_chat_action(call.message.chat.id, ChatActions.UPLOAD_VIDEO)
                    video = open(f'yt/{video_id}.mp4', 'rb')
                    sended_to_user = await bot.send_video(chat_id=chat_id, video=video, caption=caption, reply_to_message_id=message_id, supports_streaming=True)
                    sended_media = await bot.copy_message(CACHE_CHAT, chat_id, sended_to_user.message_id)
                    try:
                                cursor.execute('INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                                                        (CACHE_CHAT, sended_media.message_id, link))
                                conn.commit()
                                logger.info(f'[YouTube] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
                    except Exception as e:
                                logger.info(f'[Media] | Failed to cache {link}')
                        # deleting file after
                    os.remove(delete)
                    logger.info("%s has been removed successfuly" % delete)
                else:
                    await call.message.edit_text('Video is longer than 6 min!')
            except Exception as e:
                logger.info(f'Error when tried to dwnld: {e}')
# if not youtube download




@dp.message_handler(regexp=r'(?:https?://)?(?:www\.)?(?:vk\.com/clip|twitch\.tv/)')
async def loadvideo(message: types.Message):
    current_date = datetime.now(pytz.timezone('Asia/Almaty'))
    if current_date.tzinfo == None or current_date.\
            tzinfo.utcoffset(current_date) == None:
        logger.info("Unaware")
    else:
        logger.info("======")
    logger.info(message.chat.id)
    if message.chat.id in ignore_ids:
        return False
    else:
        user_id = message.from_user.id
        try:
            with open('user_ids.json', 'r') as file:
                user_ids = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            user_ids = []

        if user_id not in user_ids:
            user_ids.append(user_id)

        with open('user_ids.json', 'w') as file:
            json.dump(user_ids, file)

        username = message.from_user.full_name
        msg = message.text
        logger.info(f"[{current_date}] {username} : {msg}")
        link = message.text
        await bot.send_chat_action(message.chat.id, ChatActions.RECORD_VIDEO)
        cursor.execute(
                'SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (link,))
        cache_result = cursor.fetchone()
        if cache_result:
                from_chat_id, from_message_id = cache_result
                await bot.copy_message(message.chat.id, from_chat_id, from_message_id, reply_to_message_id=message_id)
        else:
            options = {'skip-download': True,
                    'format': 'mp4',
                    'outtmpl': 'video/%(id)s.%(ext)s',
                    'cookies-from-browser': 'chrome',
                    'cookies': 'cookies.txt',
                    'noplaylist': True,
                    }
            try:
                with ytd.YoutubeDL(options) as ytdl:
                    logger.info('downloading vk, tiktok, inst, twitch')
                    result = ytdl.extract_info("{}".format(link))
                    title = ytdl.prepare_filename(result)
                    ytdl.download([link])

            except:

                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton(text='❌ Close',
                                        callback_data='close'),
                )
                await bot.send_message(text=error_txt, chat_id=message.chat.id, reply_to_message_id=message_id, reply_markup=keyboard)
                
            video_title = result.get('title', None)
            uploader = result.get('uploader', None)
            video = open(f'{title}', 'rb')
            caption = f"📹: <a href='{link}'>{video_title}</a>\n\n👤: <a href='{link}'>{uploader}</a>"
            try:
                sended_to_user = await bot.send_video(chat_id=message.chat.id, 
                                                    video=video, 
                                                    caption=caption, 
                                                    reply_to_message_id=message.message_id, 
                                                    supports_streaming=True)
                sended_media = await bot.copy_message(CACHE_CHAT, message.chat.id, sended_to_user.message_id)
                try:
                    cursor.execute('INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                                            (CACHE_CHAT, sended_media.message_id, link))
                    conn.commit()
                    logger.info(f'[Media:video] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
                except Exception as e:
                    logger.info(f'[Media:video] | Failed to cache {link}')
            except:

                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton(
                        text='❌ Close',
                        callback_data='close'
                    ),
                )
                return await bot.send_message(text=error_txt, chat_id=message.chat.id, reply_to_message_id=message_id, reply_markup=keyboard)
            finally:
                # deleting file after
                os.remove(title)
                logger.info("%s has been removed successfuly" % title)


# TikTok Handler

tiktok_pattern = r'(https?://(?:www\.)?(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)/.*)'


@dp.message_handler(regexp=tiktok_pattern)
async def tiktok_downloader(message: types.Message):
    # logger.info(event.chat.id)
    if message.chat.id in ignore_ids:
        return False
    else:
        await bot.send_chat_action(message.chat.id, ChatActions.RECORD_VIDEO)
        event_chat = message.chat
        chat_id = message.chat.id
        match = re.search(tiktok_pattern, message.text)
        if match:
            link: str = match.group(1)

        try:
            logger.info(
                f"(Chat: [ID]: {event_chat.id}, [Title]: {event_chat.title}) "
                f"[Username]: {message.from_user.username}, "
                f"Link: {message.text}")
        except AttributeError:
            pass
        
        try:
            async with TikTok() as tt:
                cursor.execute('SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (link,))
                cache_result = cursor.fetchone()
                if cache_result:
                    from_chat_id, from_message_id = cache_result
                    return await bot.copy_message(
                        message.chat.id, 
                        from_chat_id, 
                        from_message_id, 
                        reply_to_message_id=message.message_id
                    )
                post_data: metadata = await tt.download(link)
                
                if post_data.type == 'images': # ? images
                    sound = await tt.download_sound(link)
                    media_list = []
                    for img in post_data.media:
                        media_list.append(InputMediaPhoto(media=open(img, 'rb')))

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
                                audio=open(sound, 'rb'), 
                                reply_to_message_id=message.message_id
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
                        with open(f'{post_data.media}', 'rb') as f:
                            caption = '<i>via @yerzhanakh_bot</i>'
                            video =  await bot.send_video(
                                chat_id=chat_id, 
                                caption=caption, 
                                reply_to_message_id=message.message_id, 
                                video=f, 
                                supports_streaming=True,
                                duration=post_data.duration,
                                width=post_data.width,
                                height=post_data.height
                            )
                            if video:
                                sended_media = await bot.copy_message(CACHE_CHAT, chat_id, video.message_id)
                                cursor.execute(
                                    'INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                                    (CACHE_CHAT, sended_media.message_id, link)
                                )
                                conn.commit()
                                logger.info(f'[TikTok] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
                                    
                                os.remove(post_data.media)
                    except Exception:   
                        logger.exception(f'ERROR DOWNLOADING TIKTOK VIDEO: {e}\nTraceback: {traceback.print_exc()}') 
                    
        except Exception as e:
            logger.exception(f'ERROR DOWNLOADING TIKTOK: {e}\nTraceback: {traceback.print_exc()}') 
# audio section here mp3/soundcloud
# audio download


@dp.callback_query_handler(text='download_mp3')
async def inline_keyboard_mp3(call: types.CallbackQuery):
    logger.info("downloading mp3 format")
    loading = "<i>Жүктеу | Loading</i>"
    await call.message.edit_text(text=loading)
    chat_id = call.message.chat.id
    cursor.execute(
                'SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (link,))
    cache_result = cursor.fetchone()
    if cache_result:
                from_chat_id, from_message_id = cache_result
                await bot.copy_message(chat_id, from_chat_id, from_message_id, reply_to_message_id=message_id)
    else:
        options = {
            'skip-download': True,
            'noplaylist': True,
            'format': 'bestaudio/best',
            'outtmpl': 'audio/%(id)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'cookies-from-browser': 'chrome',
        }
        try:
            with ytd.YoutubeDL(options) as ytdl:
                ytdl.download([link])
        except:
            logger.info(ValueError)
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(
                    text='❌ Close',
                    callback_data='close'
                ),
            )
            await bot.delete_message(call.message.chat.id, call.message.message_id)
            await bot.send_message(text=error_txt, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
        result = ytdl.extract_info("{}".format(link))
        title = ytdl.prepare_filename(result)
        video_title = result.get('title', None)
        channel = result.get('uploader_id', None)
        uploader = result.get('uploader', None)
        uploader_link = f'https://www.youtube.com/{channel}'
        delete = (f'{title}.mp3')
        audio = open(f'{title}.mp3', 'rb')

        metadata = ID3(delete)
        metadata.add(TIT2(encoding=3, text=video_title))
        metadata.add(TPE1(encoding=3, text=uploader))
        metadata.save()

        caption = f"🎧: <a href='{link}'>{video_title}</a>\n\n👤: <a href='{uploader_link}'>{uploader}</a>"
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        await bot.send_chat_action(call.message.chat.id, ChatActions.UPLOAD_AUDIO)
        sended_to_user = await bot.send_audio(chat_id=chat_id, audio=audio, caption=caption, reply_to_message_id=message_id)
        sended_audio = await bot.copy_message(CACHE_CHAT, chat_id, sended_to_user.message_id)
        try:
                cursor.execute('INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                                        (CACHE_CHAT, sended_audio.message_id, link))
                conn.commit()
                logger.info(f'[Media:track] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
        except Exception as e:
                logger.info(f'[Media:track] | Failed to cache {link}')
        # deleting file after
        os.remove(delete)
        logger.info("%s has been removed successfuly" % title)
# soundcloud track install

sc = SoundCloudTool()
SOUNDCLOUD_PATTERN = r'(https?://(?:www\.)?soundcloud\.com/[^\s]+)'


@dp.message_handler(regexp=SOUNDCLOUD_PATTERN)
async def soundload(message: types.Message):
    chat_id = message.chat.id
    message_id = message.message_id
    if chat_id in ignore_ids:
        return False
    else:
        keyboard = InlineKeyboardMarkup()
        await bot.send_chat_action(chat_id, ChatActions.RECORD_AUDIO)
        match = re.search(SOUNDCLOUD_PATTERN, message.text)
        if match:
            link = match.group(1)
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
            cursor.execute('SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (link,))
            result = cursor.fetchone()
            if result:
                from_chat_id, from_message_id = result
                return await bot.copy_message(
                    chat_id, from_chat_id, from_message_id, reply_to_message_id=message_id
                )
            else:
                logger.info("downloading mp3 format | SOUNDCLOUD")
                try:
                    track = await sc.get_track(link)
                    saved_track = await sc.save_track(track, 'audio')
                except Exception as e:
                    logger.error(f'[soundcloud]: failed to get/save track {e}')
                    keyboard.add(
                        InlineKeyboardButton(
                            text='❌ Close',
                            callback_data='close'
                        ),
                    )
                    chat_id = chat_id
                    await bot.send_message(
                        text=error_txt, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard
                    )
                audio = open(saved_track, 'rb')

                caption = f'{track.caption}\n<i>via @yerzhanakh_bot</i>'

                try:
                    await bot.send_chat_action(chat_id, ChatActions.UPLOAD_AUDIO)
                    sended_to_user = await bot.send_audio(
                        chat_id=chat_id, 
                        audio=audio,
                        caption=caption,
                        duration=track.duration,
                        performer=track.artists,
                        title=track.title,
                        reply_to_message_id=message_id
                    )
                    cached_audio = await bot.copy_message(CACHE_CHAT, chat_id, sended_to_user.message_id)
                    try:
                        cursor.execute(
                            'INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                            (CACHE_CHAT, cached_audio.message_id, link)
                        )
                        conn.commit()
                        logger.info(f'[Soundcloud:track] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
                    except Exception as e:
                        logger.info(f'[Soundcloud:track] | Failed to cache {link} | Error: {e}')
                except:
                    keyboard.add(
                        InlineKeyboardButton(
                            text='❌ Close',
                            callback_data='close'
                        ),
                    )
                    return await bot.send_message(
                        text=error_txt, 
                        chat_id=chat_id, 
                        reply_to_message_id=message_id, 
                        reply_markup=keyboard
                    )
                finally:
                    # deleting file after
                    if saved_track:
                        os.remove(saved_track)
                        logger.info("%s has been removed successfuly" % saved_track)
        else:
            logger.info(f'[soundcloud]: link not found, message: {message.text}')

def check_query(query, max_words=7):
    words = query.split()
    if len(words) > max_words:
        return False

sound_track_data: dict = {}

@dp.message_handler(commands=['sc'])
async def soundsearch(message: types.Message):
    chat_id = message.chat.id
    event_chat = message.chat
    keyboard = InlineKeyboardMarkup()
    if chat_id in ignore_ids:
        return False
    try:
        logger.info(
            f"(Chat: [ID]: {event_chat.id}, [Title]: {event_chat.title}) " 
            f"(User: [ID]: {message.from_user.id}, [Username]: {message.from_user.username} "
            f"Message: {message.text}"
        )
    except AttributeError:
        pass

    args: str = message.get_args()
    if not args:
        return await message.reply("❌ Укажите поисковый запрос. Пример: <code>/sc virtual love</code>")
    if check_query(args) == False:
        await message.reply('Search query is too long!')
        return False
    search_msg = await message.reply(f"<b>🔍 Searching:</b> <code>{args}</code>")
    try:
        results = await sc.search_tracks(args)
        
        if not results:
            return await search_msg.edit_text("🚫 Tracks not found =000")
        for track in results:
            if track.download_link is None:
                continue
            track_uuid = uuid.uuid4().hex[:8]
            sound_track_data[track_uuid] = track
            
            keyboard.add(
                InlineKeyboardButton(
                    f"{track.artists} - {track.title}", 
                    callback_data=f"soundcl_{track_uuid}"
                )
            )
        keyboard.add(
            InlineKeyboardButton(
                "❌ Close", 
                callback_data="close"
            )
        )
        await search_msg.delete()
        await message.reply(f'<b>{args.capitalize()}</b>', reply_markup=keyboard)
        
    except Exception as e:
        logger.info(f'error: {e}')
        return
    
@dp.callback_query_handler(lambda c: c.data.startswith("soundcl_"))
async def download_soundcl_track(callback_query: types.CallbackQuery):
    # await callback_query.answer()
    track_uuid = callback_query.data[len("soundcl_"):]  # get UUID
    file_path = None

    if track_uuid not in sound_track_data:
        return await bot.send_message(callback_query.from_user.id, "🚫 Track not found.")

    track = sound_track_data[track_uuid]  # get Track obj
    msg = callback_query.message  # get Message
    try:
        # Check cache first
        cursor.execute('SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (track.link,))
        result = cursor.fetchone()
        
        if result:
            from_chat_id, from_message_id = result
            await bot.copy_message(
                chat_id=callback_query.message.chat.id,
                from_chat_id=from_chat_id,
                message_id=from_message_id,
                reply_to_message_id=callback_query.message.reply_to_message.message_id if callback_query.message.reply_to_message else None
            )
            return await msg.delete()

        # If not in cache, download the track
        artist_title = f'{track.artists} - {track.title}'
        await msg.edit_text(f"<b>⬇️ Downloading:</b> <code>{artist_title}</code>")

        
        file_path = await sc.save_track(track, 'audio')
            
        if not file_path:
            raise FileNotFoundError("Failed to download track")

        await msg.edit_text(
            f"<b>⬆️ Uploading:</b> <code>{artist_title}</code>"
        )
        caption = f'{track.caption}\n<i>via @yerzhanakh_bot</i>'
            
        with open(file_path, "rb") as audio:
            user_track = await bot.send_audio(
                chat_id=msg.chat.id,
                audio=audio,
                caption=caption,
                title=track.title,
                performer=track.artists,
                duration=track.duration,
                reply_to_message_id=callback_query.message.reply_to_message.message_id if callback_query.message.reply_to_message else None
            )
            cached_track = await bot.copy_message(
                CACHE_CHAT, 
                msg.chat.id,
                user_track.message_id
            )
                
            try:
                cursor.execute(
                    'INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                    (CACHE_CHAT, cached_track.message_id, track.link)
                )
                conn.commit()
                logger.info(f'[Soundcloud: track] | Track {track.link} cached successfully')
            except Exception as e:
                logger.error(f'[Soundcloud: track] | Failed to cache track {track.link} | Error: {e}')
            
            await msg.delete()
            
    except Exception as e:
        error_message = f"❌ Error while downloading track:"
        logger.error(f'[Soundcloud: track] | {str(e)}')
        await msg.edit_text(error_message, parse_mode="HTML")
        
    finally:
        if track_uuid in sound_track_data:
            del sound_track_data[track_uuid]
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f'Failed to remove temporary file {file_path}: {e}')


@dp.message_handler(regexp=r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)')
async def downloading(message: types.Message):
    current_date = datetime.now(pytz.timezone('Asia/Almaty'))
    if current_date.tzinfo == None or current_date.\
            tzinfo.utcoffset(current_date) == None:
        logger.info("Unaware")    
    else:
        logger.info("======")
    username = message.from_user.full_name
    msg = message.text
    logger.info(f"[{current_date}] {username} : {msg}")
    if message.chat.id in ignore_ids:
        return False
    else:
        global link
        link = await tools.convert_share_urls(message.text)
        global message_id
        message_id = message.message_id
        # messages texts
        text = text_txt
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text='📹', callback_data='download_mp4'),
            InlineKeyboardButton(text='🔊', callback_data='download_mp3'),
            # InlineKeyboardButton(text='Image (TikTok)',
            #                      callback_data='download_img'),
        )
        return await message.reply(text=text, reply_markup=keyboard)


async def download_playlist_mp3(playlist_url, chat_id, download_path, event_message_id, message):
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    ydl_opts = {
        'format': 'bestaudio/best',
        'writethumbnail': True,
        'embedthumbnail': True,
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            },
            {
                'key': 'EmbedThumbnail',
            }
        ],
        'outtmpl': f'{download_path}track_%(id)s.%(ext)s',
    }

    with ytd.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        num_tracks = len(info['entries'])
        await bot.edit_message_text(f'<b>Downloading</b> 📥 | <a href="{playlist_url}">Playlist ({num_tracks} tracks)</a>',
                                    chat_id=chat_id, message_id=event_message_id, parse_mode='html', disable_web_page_preview=True)

        for entry in info['entries']:
            if entry:
                video_url = entry['webpage_url']
                cursor.execute(
                    'SELECT chat_id, message_id FROM audio_cache WHERE audio_link = ?', (video_url,))
                result = cursor.fetchone()

                try:
                    if result:
                        logger.info('[playlist] track already downloaded')
                        cached_chat_id, message_id = result
                        return await bot.copy_message(chat_id, cached_chat_id, message_id, reply_to_message_id=event_message_id)
                    else:
                        try:
                            ids = entry['id']
                            file_name = f'track_{ids}'
                            title = entry['title']
                            uploader = entry['uploader']
                        except KeyError:
                            uploader = 'None'
                        ydl.download([video_url])
                        video_path = download_path + file_name + '.mp3'
                        caption = f"<a href='{video_url}'>{title}</a>"

                        tag = TinyTag.get(video_path)
                        duration = int(tag.duration)

                        cached_track = await bot.send_audio(chat_id, 
                                                audio=open(video_path, 'rb'), 
                                                caption=caption, 
                                                performer=uploader,
                                                title=title, 
                                                duration=duration,
                                                reply_to_message_id=event_message_id)

                        cursor.execute('INSERT INTO audio_cache (chat_id, message_id, audio_link) VALUES (?, ?, ?)',
                                        (chat_id, cached_track.message_id, video_url))
                        conn.commit()
                        logger.info('[playlist] track successfully cached')

                        if os.path.exists(video_path):
                            os.remove(video_path)
                            logger.info('Video deleted successfully')
                except ChatNotFound as e:
                    print(f'Chat Not Found trying to download: {e}')
                    try:
                        ids = entry['id']
                        file_name = f'track_{ids}'
                        title = entry['title']
                        uploader = entry['uploader']
                    except KeyError:
                        uploader = 'None'
                    ydl.download([video_url])
                    video_path = download_path + file_name + '.mp3'
                    caption = f"<a href='{video_url}'>{title}</a>"

                    tag = TinyTag.get(video_path)
                    duration = int(tag.duration)

                    cached_track = await bot.send_audio(chat_id, 
                                            audio=open(video_path, 'rb'), 
                                            caption=caption, 
                                            performer=uploader,
                                            title=title, 
                                            duration=duration,
                                            reply_to_message_id=event_message_id)

                    cursor.execute('INSERT INTO audio_cache (chat_id, message_id, audio_link) VALUES (?, ?, ?)',
                                    (chat_id, cached_track.message_id, video_url))
                    conn.commit()
                    logger.info('[playlist] track successfully cached')

                    if os.path.exists(video_path):
                        os.remove(video_path)
                        logger.info('Video deleted successfully')

        await bot.edit_message_text(f'<b>Done</b> ✅ | <a href="{playlist_url}">Playlist</a>',
                                    chat_id=chat_id, message_id=event_message_id, parse_mode='html', disable_web_page_preview=True)
        logger.info('[playlist] Finished downloading')



@dp.message_handler(commands=['playlist'])
async def mp3playlist_handler_download(message: types.Message):
    message_text = message.text
    url_pattern = r'/playlist\s+(https?://\S+)'

    match = re.search(url_pattern, message_text)
    if match:
        playlist_url = match.group(1)

        chat_id = message.chat.id
        to_edit = await bot.send_message(chat_id, "<b>Starting to download!</b> | <code>Type: [playlist]</code>",
                                         reply_to_message_id=message.message_id, parse_mode='html')
        download_path = 'audio/'

        try:
            await download_playlist_mp3(playlist_url, chat_id, download_path, to_edit.message_id, message)
        except Exception as e:
            print(f'Error in playlist download: {e}')
    else:
        await message.reply("Please provide a valid playlist URL.\n\nExample:https://soundcloud.com/damirtag/sets/for-gym-by-damirtag")


""" Instagram POSTS """

@dp.message_handler(regexp=r'(https?://)?(www\.)?instagram\.com/p/.*')
async def inst_photos_handler(message: types.Message):
    event_chat = message.chat
    if event_chat.id in ignore_ids:
        return False

    try:
        logger.info(
            f"(Chat: [ID]: {event_chat.id}, [Title]: {event_chat.title}) (User: [ID]: {message.from_user.id}, "
            f"[Username]: {message.from_user.username}, [FN]: {message.from_user.first_name}, [SN]: {message.from_user.last_name}) "
            f"Message: {message.text}"
        )
    except AttributeError:
        pass

    await bot.send_chat_action(message.chat.id, ChatActions.UPLOAD_PHOTO)
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
                # Убираем caption у всех кроме первой группы
                for item in chunk:
                    item.caption = ""
            await bot.send_media_group(event_chat.id, media=chunk, reply_to_message_id=message.message_id)
    else:
        await message.reply("❌ Failed to retrieve any images.")

    shutil.rmtree(file_path)
    logger.info(f"[Instagram:post] | {shortcode} folder removed successfully")


async def download_inst_post(session: aiohttp.ClientSession, url, download_dir):
    async with semaphore:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
            if response.status == 404:
                logger.info(f"[Instagram:post] | No file found at {url} (404)")
                return False
            
            if response.status != 200:
                logger.warning(f"[Instagram:post] | Error fetching {url}. Status: {response.status}")
                return False

            # Detect file type from Content-Type header
            content_type = response.headers.get('Content-Type', '')
            if "image" in content_type:
                ext = ".jpg"
            elif "video" in content_type:
                ext = ".mp4"
            else:
                logger.warning(f"[Instagram:post] | Unsupported content type: {content_type} at {url}")
                return False

            content = await response.read()
            if len(content) < 500:  # Avoid empty pages (0-byte or small HTML error pages)
                logger.warning(f"[Instagram:post] | Empty file detected at {url}. Skipping.")
                return False

            parsed_url = urlparse(url)
            filename = unquote(os.path.basename(parsed_url.path)) + ext
            file_path = os.path.join(download_dir, filename)

            with open(file_path, 'wb') as f:
                f.write(content)

            logger.info(f"[Instagram:post] | Downloaded: {filename}")
            return True


@dp.message_handler(regexp=r'(https?://)?(www\.)?instagram\.com/(reel|share|tv)/.*')
async def inst_reels_handler(message: types.Message):
    event_chat = message.chat

    try:
        logger.info(
            f"(Chat: [ID]: {event_chat.id}, [Title]: {event_chat.title}) (User: [ID]: {message.from_user.id}, [Username]: {message.from_user.username}, [FN]: {message.from_user.first_name}, [SN]: {message.from_user.last_name}) Message: {message.text}")
    except AttributeError:
        pass

    if event_chat.id in ignore_ids:
        return False
    else:

        # username, fullname = await get_user_info(event_chat.id)
        reel_url = await tools.convert_share_urls(message.text)

        await bot.send_chat_action(message.chat.id, ChatActions.RECORD_VIDEO)
        
        cursor.execute(
                'SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (reel_url,))
        result = cursor.fetchone()
        if result:
            from_chat_id, from_message_id = result
            return await bot.copy_message(event_chat.id, from_chat_id, from_message_id, reply_to_message_id=message.message_id)
        else:
            shortcode = reel_url.split("/")[-1]

            video_filename = f'{shortcode}.mp4'
            url = f'https://ddinstagram.com/videos/{shortcode}/1'

            try:
                if not os.path.exists(video_filename):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as response:
                            if response.status == 200:
                                total_size = int(response.headers.get('content-length', 0))
                                with open(video_filename, 'wb') as f, tqdm(
                                        total=total_size, unit='B', unit_scale=True, desc=video_filename) as pbar:
                                    async for chunk in response.content.iter_any():
                                        f.write(chunk)
                                        pbar.update(len(chunk))

                                logger.info(f"[Instagram:video] | Downloaded and saved as {video_filename}")
                            else:
                                logger.info(f"[Instagram:video] | Can't get data from {url}| Response: {response.status}")
                else:
                    logger.info(f"[Instagram:video] | {video_filename} already exists. Skipping download.")

                caption = f'📹 <i>via @yerzhanakh_bot</i>'

                logger.info(f'[Instagram:video] | Sending... [{shortcode}]')

                with open(video_filename, 'rb') as video:
                    logger.info(f'Sending {video_filename}')
                    sended_to_user = await bot.send_video(event_chat.id, video, caption=caption, reply_to_message_id=message.message_id, supports_streaming=True)
                    sended_video = await bot.copy_message(CACHE_CHAT, event_chat.id, sended_to_user.message_id)

                cursor.execute('INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',(CACHE_CHAT, sended_video.message_id, reel_url))
                conn.commit()
                if 'video_filename' in locals():
                    os.remove(video_filename)
                    logger.info("% s has been removed successfully" % video_filename)    
            except Exception as e:
                logger.info(f'[Instagram:video] | {e}')
                


if __name__ == '__main__':
    logger.info(f"{ConsoleColors.OKGREEN}Starting bot{ConsoleColors.ENDC}")
    loop = asyncio.get_event_loop()
    executor.start_polling(dp, skip_updates = True)
