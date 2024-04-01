# INIT START
from config import TOKEN

# TEXT FILES IMPORT BEGIN
from allText import start_txt, text_txt, error_txt, help_txt, update_txt
# TEXT FILES IMPORT END

import pytz
import yt_dlp as ytd
import os, re
import sqlite3
import json
import aiohttp
import shutil
import logging
import base64


from tools import Tools, ConsoleColors, Platforms
from pin_crawler import PinterestScraper
from TikTok import TikTok
from convert import Converter
from database import Database
from routes import Routes


from mutagen.id3 import ID3, TIT2, TPE1, APIC
from random import randrange
from tinytag import TinyTag
from datetime import datetime
from urllib.parse import urlparse, unquote
from tqdm.asyncio import tqdm
from aiogram.utils.exceptions import ChatNotFound


from aiogram.dispatcher.filters import Text
from aiogram import Dispatcher, Bot, executor, types
from aiogram import asyncio
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatActions, InputMediaPhoto, InputMediaVideo, ParseMode
# =========
storage = MemoryStorage()
semaphore = asyncio.Semaphore(10)
#BOT INIT
bot = Bot(TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=storage)
tools = Tools()
#DATABASE
conn = sqlite3.connect('audio_cache.db')
cursor = conn.cursor()
#LOGER
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()
DAMIR_USER_ID = 1038468423
GITHUB_REPO = 'None'

pl = Platforms()

# =========
# INIT FINISH

async def get_user_info(user_id):
    try:
        user = await bot.get_chat(user_id)
        username = user.username
        fullname = user.full_name
        return username, fullname
    except ChatNotFound:
        return None, None
        print('chat not found skipping...')

@dp.message_handler(commands='start')
async def hello(message: types.Message):
    database = Database('database/users.db')
    if message.chat.type == 'private':
        username, fullname = await get_user_info(message.from_user.id)
        database.insert_data('users', data=(message.from_user.id, username, fullname))
    # user_id = message.from_user.id
    # try:
    #     with open('user_ids.json', 'r') as file:
    #         user_ids = json.load(file)
    # except (FileNotFoundError, json.JSONDecodeError):
    #     user_ids = []

    # if user_id not in user_ids:
    #     user_ids.append(user_id)

    # with open('user_ids.json', 'w') as file:
    #     json.dump(user_ids, file)

    start = start_txt
    await message.reply(text=start)


@dp.message_handler(commands=['sendall'])
async def send_all(message: types.Message):
    if message.from_user.id == 1038468423:
        try:
            with open('user_ids.json', 'r') as file:
                user_ids = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            user_ids = []

        for user_id in user_ids:
            await bot.send_photo(chat_id=user_id, photo=open('update_@yerzhan_bot.jpg', 'rb'), caption=update_txt)
    else:
        return False


@dp.message_handler(commands='help', commands_prefix='!/')
async def help(message: types.Message):
    help = help_txt
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            text='Dev 🧑‍💻', url='https://github.com/damirTAG'),
    )
    await message.reply(text=help, reply_markup=keyboard)

# close button


@dp.callback_query_handler(text="close")
async def close(call: types.CallbackQuery):
    await bot.delete_message(call.message.chat.id, call.message.message_id)


# roll
@dp.message_handler(commands=['roll', 'ролл'], commands_prefix='!/.')
async def rate(message: types.Message):
    nick = message.from_user.first_name
    chat_id = message.chat.id
    random = (randrange(101))
    roll = f'🎱 <b>{nick}</b> роллит! [1-100]. Выпадает: <b>{random}</b>!'
    return await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=roll)


# get routes from https://mountain.kz/
current_page = 0

@dp.message_handler(commands=['routes'], commands_prefix='!/.')
async def routes_handler(message: types.Message):
    global message_id
    message_id = message.message_id
    routes = Routes()
    route_data = routes.get_routes()
    
    # Paginate route names into groups of 10
    chunks = [route_data[i:i + 10] for i in range(0, len(route_data), 10)]
    current_page = 0
    
    keyboard = InlineKeyboardMarkup()
    
    for route in chunks[current_page]:
        keyboard.add(InlineKeyboardButton(f'⛰ {route["name"]}', callback_data=f"route_{route['id']}"))
    
    keyboard.add(
        InlineKeyboardButton("⬅️ Next", callback_data="next"),
    )

    await message.reply("Выберите маршрут:", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith('route_'))
async def route_handler(callback_query: types.CallbackQuery):
    routes = Routes()
    route_id = callback_query.data.replace('route_', '')
    route_name = [route["name"] for route in routes.get_routes() if str(route["id"]) == route_id][0]

    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)

    result = await routes.parse(route_id)
    description, route_images = result
    
    if route_images:
        image_filenames = await routes.get_route_images(route_images, route_id)
        print("Image Filenames:", image_filenames)

        media_group = [types.InputMediaPhoto(media=open(image_filename, 'rb')) for image_filename in image_filenames]
        await bot.send_media_group(callback_query.message.chat.id, media=media_group, reply_to_message_id=message_id)
        for image in image_filenames:
            os.remove(image)
            print(f'{image} removed successfully')
    
    await bot.send_message(callback_query.message.chat.id, text=f'<b>Маршрут: {route_name}</b>\n\n{description}', reply_to_message_id=message_id)
    

@dp.callback_query_handler(lambda c: c.data == 'next')
async def next_page(callback_query: types.CallbackQuery):
    global current_page
    current_page += 1
    
    routes = Routes()
    route_data = routes.get_routes()
    chunks = [route_data[i:i + 10] for i in range(0, len(route_data), 10)]
    
    if current_page < len(chunks):
        keyboard = InlineKeyboardMarkup()

        for route in chunks[current_page]:
            keyboard.add(InlineKeyboardButton(f'⛰ {route["name"]}', callback_data=f"route_{route['id']}"))
        
        if current_page > 0:
            keyboard.add(InlineKeyboardButton("Previous ➡️", callback_data="prev"))
        if current_page < len(chunks) - 1:
            keyboard.add(InlineKeyboardButton("⬅️ Next", callback_data="next"))

        await bot.edit_message_reply_markup(
            callback_query.message.chat.id, 
            callback_query.message.message_id, 
            reply_markup=keyboard
        )
    else:
        await bot.answer_callback_query(callback_query.id, "You are already on the last page", show_alert=True)


@dp.callback_query_handler(lambda c: c.data == 'prev')
async def prev_page(callback_query: types.CallbackQuery):
    global current_page
    current_page -= 1
    
    routes = Routes()
    route_data = routes.get_routes()
    chunks = [route_data[i:i + 10] for i in range(0, len(route_data), 10)]

    if current_page >= 0: 
        keyboard = InlineKeyboardMarkup()

        for route in chunks[current_page]:
            keyboard.add(InlineKeyboardButton(f'⛰ {route["name"]}', callback_data=f"route_{route['id']}"))
        
        if current_page > 0:
            keyboard.add(InlineKeyboardButton("Previous ➡️", callback_data="prev"))
        if current_page < len(chunks) - 1:
            keyboard.add(InlineKeyboardButton("⬅️ Next", callback_data="next"))

        await bot.edit_message_reply_markup(
            callback_query.message.chat.id, 
            callback_query.message.message_id, 
            reply_markup=keyboard
        )
    else:
        await bot.answer_callback_query(callback_query.id, "You are already on the first page", show_alert=True)

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
@dp.async_task
async def inline_keyboard_mp4(call: types.CallbackQuery):
    print("downloading mp4 format")
    loading = "<i>Жүктеу | Loading</i>"
    await call.message.edit_text(text=loading)
    chat_id = call.message.chat.id
    database = Database('database/users.db')
    if call.message.chat.type == 'private':
        username, fullname = await get_user_info(chat_id)
        database.insert_data('users', data=(chat_id, username, fullname))

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
            'outtmpl': 'yt/%(id)s.%(ext)s',
        }
        try:
            with ytd.YoutubeDL(options) as ytdl:
                ytdl.download([link])
        except:
            print(ValueError)
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(text='❌ Жабу | Close',
                                    callback_data='close'),
            )
            await bot.delete_message(call.message.chat.id, call.message.message_id)
            await bot.send_message(text=error_txt, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
        result = ytdl.extract_info("{}".format(link))
        title = ytdl.prepare_filename(result)
        video_title = result.get('title', None)
        channel = result.get('uploader_id', None)
        uploader = result.get('uploader', None)
        uploader_link = f'https://www.youtube.com/{channel}'
        delete = (f'{title}')
        video = open(f'{title}', 'rb')
        caption = f"📹: <a href='{link}'>{video_title}</a>\n\n👤: <a href='{uploader_link}'>{uploader}</a>"
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        await bot.send_chat_action(call.message.chat.id, ChatActions.UPLOAD_VIDEO)
        sended_media = await bot.send_video(chat_id=chat_id, video=video, caption=caption, reply_to_message_id=message_id, supports_streaming=True)
        try:
                    cursor.execute('INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                                            (chat_id, sended_media.message_id, link))
                    conn.commit()
                    print(f'[YouTube] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
        except Exception as e:
                    print(f'[Media] | Failed to cache {link}')
        # deleting file after
        os.remove(delete)
        print("%s has been removed successfuly" % title)

# if not youtube download

ignore_ids = [-1001559555304, -1001919227306, -1001987624296]   # -1001559555304, -1001919227306, -1001987624296


@dp.message_handler(regexp=r'(?:https?://)?(?:www\.)?(?:vk\.com/clip|twitch\.tv/)')
@dp.async_task
async def loadvideo(message: types.Message):
    current_date = datetime.now(pytz.timezone('Asia/Almaty'))
    if current_date.tzinfo == None or current_date.\
            tzinfo.utcoffset(current_date) == None:
        print("Unaware")
    else:
        print("======")
    print(message.chat.id)
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
        print(f"[{current_date}] {username} : {msg}")
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
                    print('downloading vk, tiktok, inst, twitch')
                    result = ytdl.extract_info("{}".format(link))
                    title = ytdl.prepare_filename(result)
                    ytdl.download([link])

            except:

                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton(text='❌ Жабу | Close',
                                        callback_data='close'),
                )
                await bot.send_message(text=error_txt, chat_id=message.chat.id, reply_to_message_id=message_id, reply_markup=keyboard)
                
            video_title = result.get('title', None)
            uploader = result.get('uploader', None)
            video = open(f'{title}', 'rb')
            caption = f"📹: <a href='{link}'>{video_title}</a>\n\n👤: <a href='{link}'>{uploader}</a>"
            try:
                sended_media = await bot.send_video(chat_id=message.chat.id, video=video, caption=caption, reply_to_message_id=message.message_id, supports_streaming=True)
                try:
                    cursor.execute('INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                                            (message.chat.id, sended_media.message_id, link))
                    conn.commit()
                    print(f'[Media:video] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
                except Exception as e:
                    print(f'[Media:video] | Failed to cache {link}')
            except:

                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton(text='❌ Жабу | Close',
                                        callback_data='close'),
                )
                return await bot.send_message(text=error_txt, chat_id=message.chat.id, reply_to_message_id=message_id, reply_markup=keyboard)
            finally:
                # deleting file after
                os.remove(title)
                print("%s has been removed successfuly" % title)


# TikTok Handler

tiktok_pattern = r'(https?://(?:www\.)?(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)/.*)'


@dp.message_handler(regexp=tiktok_pattern)
@dp.async_task
async def tiktok_downloader(message: types.Message):
    # print(event.chat.id)
    if message.chat.id in ignore_ids:
        return False
    else:
        chat = message.chat.id

        database = Database('database/users.db')
        if message.chat.type == 'private':
            username, fullname = await get_user_info(chat)
            database.insert_data('users', data=(chat, username, fullname))

        link = message.text
        print(link)

        tt_module = TikTok()
        await tt_module.init(link)
        caption = tt_module.construct_caption_posts()
    try:
        sorted_images = await tt_module.download_photos()

        # DOWNLOAD SOUND
        audio_filename = await tt_module.download_sound()
        a_caption = tt_module.construct_caption_audio()
        try:
            media_group = [InputMediaPhoto(media=open(img, 'rb'), caption=caption) for img in sorted_images.values()]
            await bot.send_media_group(chat_id=chat, media=media_group, reply_to_message_id=message.message_id)
            await asyncio.sleep(0.5)
            try:
                await bot.send_audio(
                    chat_id=chat, caption=a_caption, audio=open(audio_filename, 'rb'), reply_to_message_id=message.message_id)
            except Exception as e:
                print(f"Error with sound sending: {e}")
            tt_module.__del_photos__()
            tt_module.__del_sound__()
        except Exception as e:
            print(f"Error occured: {e}")
    except KeyError:
        cursor.execute(
                'SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (link,))
        cache_result = cursor.fetchone()
        if cache_result:
                from_chat_id, from_message_id = cache_result
                await bot.copy_message(message.chat.id, from_chat_id, from_message_id, reply_to_message_id=message_id)
        else:
            video = await tt_module.download_video()

            try:
                with open(f'{video}', 'rb') as f:
                        sended_media = await bot.send_video(chat_id=chat, caption=caption, reply_to_message_id=message.message_id, video=f, supports_streaming=True)
                try:
                    cursor.execute('INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                                            (chat.id, sended_media.message_id, link))
                    conn.commit()
                    print(f'[TikTok] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
                except Exception as e:
                    print(f'[TikTok] | Failed to cache {link}')        
                    tt_module.__del_video__()
            except Exception as e:
                    print(f"Error occured: {e}")



# audio section here mp3/soundcloud
# audio download


@dp.callback_query_handler(text='download_mp3')
@dp.async_task
async def inline_keyboard_mp3(call: types.CallbackQuery):
    print("downloading mp3 format")
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
            print(ValueError)
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(text='❌ Жабу | Close',
                                    callback_data='close'),
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
        sended_audio = await bot.send_audio(chat_id=chat_id, audio=audio, caption=caption, reply_to_message_id=message_id)
        try:
                cursor.execute('INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                                        (chat_id, sended_audio.message_id, link))
                conn.commit()
                print(f'[Media:track] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
        except Exception as e:
                print(f'[Media:track] | Failed to cache {link}')
        # deleting file after
        os.remove(delete)
        print("%s has been removed successfuly" % title)
# soundcloud track install


@dp.message_handler(regexp=r'(?:https?://)?(?:www\.)?(?:soundcloud\.com)')
@dp.async_task
async def soundload(message: types.Message):
    if message.chat.id in ignore_ids:
        return False
    else:
        await bot.send_chat_action(message.chat.id, ChatActions.RECORD_AUDIO)
        msg = message.text
        if ' https://on.' in msg:
            link = await tools.convert_share_urls(msg)
        else:
            link = msg
        current_date = datetime.now(pytz.timezone('Asia/Almaty'))
        if current_date.tzinfo == None or current_date.\
                tzinfo.utcoffset(current_date) == None:
            print("Unaware")
        else:
            print("======")
        username = message.from_user.full_name
        msg = message.text
        print(f"[{current_date}] {username} : {msg}")
        cursor.execute(
                    'SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (link,))
        result = cursor.fetchone()
        if result:
                from_chat_id, from_message_id = result
                await bot.copy_message(message.chat.id, from_chat_id, from_message_id, reply_to_message_id=message.message_id)
        else:
            print("downloading mp3 format | SOUNDCLOUD")
            options = {
                'skip-download': True,
                'writethumbnail': True,
                'embedthumbnail': True,
                'noplaylist': True,
                'format': 'bestaudio/best',
                'outtmpl': 'audio/%(id)s',
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
                # 'cookies-from-browser': 'chrome',
            }
            try:
                with ytd.YoutubeDL(options) as ytdl:
                    ytdl.download([link])
            except:
                print(ValueError)
                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton(text='❌ Жабу | Close',
                                        callback_data='close'),
                )
                chat_id = message.chat.id
                await bot.send_message(text=error_txt, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
            result = ytdl.extract_info("{}".format(link))
            title = ytdl.prepare_filename(result)
            delete = (f'{title}.mp3')
            audio = open(f'{title}.mp3', 'rb')
            none = "Damir the best"
            video_title = result.get('title', none)
            uploader = result.get('uploader', none)
            uploader_id = result.get('uploader_id', none)
            uploader_link = f'https://soundcloud.com/{uploader_id}'

            metadata = ID3(delete)
            metadata.add(TIT2(encoding=3, text=video_title))
            metadata.add(TPE1(encoding=3, text=uploader))
            metadata.save()

            username = message.from_user.username
            caption = f'<a href="{link}">{video_title}</a> — <a href="{uploader_link}">{uploader}</a>'
            chat_id = message.chat.id
            message_id = message.message_id
            try:
                await bot.send_chat_action(message.chat.id, ChatActions.UPLOAD_AUDIO)
                sended_audio = await bot.send_audio(chat_id=chat_id, audio=audio, caption=caption, reply_to_message_id=message_id)
                try:
                    cursor.execute('INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                                            (chat_id, sended_audio.message_id, link))
                    conn.commit()
                    print(f'[Soundcloud:track] | {ConsoleColors.OKGREEN}{link} cached{ConsoleColors.ENDC}')
                except Exception as e:
                    print(f'[Soundcloud:track] | Failed to cache {link}')
            except:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton(text='❌ Жабу | Close',
                                        callback_data='close'),
                )
                chat_id = message.chat.id
                return await bot.send_message(text=error_txt, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
            finally:
                # deleting file after
                os.remove(delete)
                print("%s has been removed successfuly" % title)


@dp.message_handler(regexp=r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)')
@dp.async_task
async def downloading(message: types.Message):
    current_date = datetime.now(pytz.timezone('Asia/Almaty'))
    if current_date.tzinfo == None or current_date.\
            tzinfo.utcoffset(current_date) == None:
        print("Unaware")    
    else:
        print("======")
    username = message.from_user.full_name
    msg = message.text
    print(f"[{current_date}] {username} : {msg}")
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


async def download_playlist_mp3(playlist_url, chat_id, download_path, event_message_id):
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

                if result:
                    print('[playlist] track already downloaded')
                    chat_id, message_id = result
                    cached_track = await bot.copy_message(chat_id, message_id)

                    await bot.send_message(chat_id, cached_track)
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

                    await bot.send_audio(chat_id, audio=open(video_path, 'rb'), caption=caption, performer=uploader,
                                         title=title, duration=duration)

                    cursor.execute('INSERT INTO audio_cache (chat_id, message_id, audio_link) VALUES (?, ?, ?)',
                                   (chat_id, message_id, video_url))
                    conn.commit()
                    print('[playlist] track successfully cached')

                    if os.path.exists(video_path):
                        os.remove(video_path)
                        print('Video deleted successfully')

    await bot.edit_message_text(f'<b>Done</b> ✅ | <a href="{playlist_url}">Playlist</a>',
                                chat_id=chat_id, message_id=event_message_id, parse_mode='html', disable_web_page_preview=True)
    print('[playlist] Finished downloading')



@dp.message_handler(commands=['playlist'], commands_prefix=['/.'])
async def mp3playlist_handler_download(message: types.Message):
    playlist_url = message.text.split(' ', 1)
    if len(playlist_url) > 1:
        playlist_url = playlist_url[1].strip()
    else:
        playlist_url = None

    if playlist_url:
        chat_id = message.chat.id
        to_edit = await bot.send_message(chat_id, "<b>Starting to download!</b> | <code>Type: [playlist]</code>",
                                         reply_to_message_id=message.message_id, parse_mode='html')
        download_path = 'audio/'

        await download_playlist_mp3(playlist_url, chat_id, download_path, to_edit.message_id)
    else:
        await message.reply("Please provide a valid playlist URL.\n\nExample:https://soundcloud.com/damirtag/sets/for-gym-by-damirtag")	


""" Instagram POSTS """

@dp.message_handler(regexp=r'(https?://)?(www\.)?instagram\.com/p/.*')
@dp.async_task
async def inst_photos_handler(message: types.Message):
    event_chat = message.chat
    if event_chat.id in ignore_ids:
        return False
    try:
        logger.info(
                f"(Chat: [ID]: {event_chat.id}, [Title]: {event_chat.title}) (User: [ID]: {message.from_user.id}, [Username]: {message.from_user.username}, [FN]: {message.from_user.first_name}, [SN]: {message.from_user.last_name}) Message: {message.text}")
    except AttributeError:
        pass

    database = Database('database/users.db')
    if message.chat.type == 'private':
        username, fullname = await get_user_info(event_chat.id)
        database.insert_data('users', data=(event_chat.id, username, fullname))
    await bot.send_chat_action(message.chat.id, ChatActions.UPLOAD_PHOTO)
    post_url = message.text
    shortcode = post_url.split("/")[-2]

    urls_to_check = [f'https://ddinstagram.com/images/{shortcode}/{i}' for i in range(1, 11)]

    try:
        file_path = f'{shortcode}'
        os.makedirs(file_path, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(urls_to_check):
                await download_image(session, url, file_path)

        caption = f'🖼 <a href="https://instagram.com/p/{shortcode}">LINK</a>\n\n<i>via @yerzhanakh_bot</i>'

        media_list = []
        for filename in os.listdir(file_path):
            file_full_path  = os.path.join(file_path, filename)
            if filename.endswith('.mp4'):
                media_list.append(InputMediaVideo(media=open(file_full_path , 'rb'), caption=caption))
            elif filename.endswith('.jpg') or filename.endswith('.png'):
                media_list.append(InputMediaPhoto(media=open(file_full_path , 'rb'), caption=caption))

        # Sort the images
        try:
            print(f'[Instagram:post] | Sorting...')
            sorted_media = sorted(media_list, key=lambda x: x.caption)
        except Exception as e:
            print(f'[Instagram:post] | ERROR WHEN TRIED TO SORT {e}')
        
        print(f'[Instagram:post] | Sending... {shortcode}')
        sended_media = await bot.send_media_group(event_chat.id, media=sorted_media, reply_to_message_id=message.message_id)
        try:
            cursor.execute('INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                                    (event_chat.id, sended_media.message_id, post_url))
            conn.commit()
            print(f'[Instagram:post] | {ConsoleColors.OKGREEN}{shortcode} cached{ConsoleColors.ENDC}')
        except Exception as e:
            print(f'[Instagram:post] | Failed to cache {shortcode}')
    except Exception as e:
        print(f'[Instagram:post] | {ConsoleColors.FAIL}ERROR {e}{ConsoleColors.ENDC}')
    finally:
        if 'file_path' in locals():
            shutil.rmtree(file_path)
            print("[Instagram:post] | % s has been removed successfully" % file_path)


async def download_image(session, url, download_dir):
    async with semaphore:
        async with session.head(url) as response:
            if response.status == 302:
                redirect_url = response.headers['Location']
                print(f"[Instagram:post] | Redirecting to https://scontent.cdninstagram.com/")

                parsed_url = urlparse(redirect_url)
                filename = unquote(os.path.basename(parsed_url.path))
                image_filename = f'{download_dir}/{filename}'
                # print(filename)
                async with session.get(redirect_url) as download_response:
                    if download_response.status == 200:
                        total_size = int(download_response.headers.get('content-length', 0))
                        with open(image_filename, 'wb') as f, tqdm(
                                total=total_size, unit='B', unit_scale=True, desc=image_filename) as pbar:
                            async for chunk in download_response.content.iter_any():
                                f.write(chunk)
                                pbar.update(len(chunk))
                    else:
                        print(f"[Instagram:post] | Error downloading {url}. Status code: {download_response.status}")
            elif response.status == 404:
                pass
            else:
                print(f"[Instagram:post] | Error checking {url}. Status code: {response.status}")


@dp.message_handler(regexp=r'(https?://)?(www\.)?instagram\.com/(reel|reels)/.*')
@dp.async_task
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
        database = Database('database/users.db')
        if message.chat.type == 'private':
            username, fullname = await get_user_info(event_chat.id)
            database.insert_data('users', data=(event_chat.id, username, fullname))
        await bot.send_chat_action(message.chat.id, ChatActions.RECORD_VIDEO)
        
        reel_url = await tools.convert_share_urls(message.text)
        cursor.execute(
                'SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (reel_url,))
        result = cursor.fetchone()
        if result:
            from_chat_id, from_message_id = result
            await bot.copy_message(event_chat.id, from_chat_id, from_message_id, reply_to_message_id=message.message_id)
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

                                print(f"[Instagram:video] | Downloaded and saved as {video_filename}")
                else:
                    print(f"[Instagram:video] | {video_filename} already exists. Skipping download.")

                caption = f'📹 <i>via @yerzhanakh_bot</i>'

                print(f'[Instagram:video] | Sending... [{shortcode}]')

                with open(video_filename, 'rb') as video:
                    sended_video = await bot.send_video(event_chat.id, video, caption=caption, parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id)

                if hasattr(sended_video, 'message_id'):
                    cursor.execute('INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',
                                    (event_chat.id, sended_video.message_id, reel_url))
                    conn.commit()
            except Exception as e:
                print(f'[Instagram:video] | {e}')
            finally:
                if 'video_filename' in locals():
                    os.remove(video_filename)
                    print("% s has been removed successfully" % video_filename)
                    

if __name__ == '__main__':
    logger.info(f"{ConsoleColors.OKGREEN}Starting bot{ConsoleColors.ENDC}")
    executor.start_polling(dp, skip_updates=True)
