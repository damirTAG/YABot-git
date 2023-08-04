from config import TOKEN
import os
import logging
from convert import Converter
from datetime import datetime
import pytz
import yt_dlp as ytd
from aiogram import Dispatcher, Bot, executor, types
from aiogram import asyncio
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatActions
# from aiogram.dispatcher.filters import Text
# from savify import Savify
# from savify.types import Type, Format, Quality
# from savify.utils import PathHolder
# from requests import get
# from json import loads
# from bs4 import BeautifulSoup as bs
# =========
storage = MemoryStorage()
bot = Bot(TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()
# =========


@dp.message_handler(commands='start')
async def hello(message: types.Message):
    start = "🏴󠁧󠁢󠁥󠁮󠁧󠁿󠁧󠁢󠁥󠁮󠁧󠁿 Hello there! This is YouTube/TikTok/Reels video and audio bot installer\n🇰🇿 Сәлем! Бұл YouTube/TikTok/Reels/Twitch Clips/SoundcloudTracks бот орнатушысы"
    await message.reply(text=start)


# close button
@dp.callback_query_handler(text="close")
async def close(call: types.CallbackQuery):
    await bot.delete_message(call.message.chat.id, call.message.message_id)

# speech rec


@dp.message_handler(content_types=['voice', 'video_note'])
async def get_audio_messages(message: types.Message):
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
    message_text = f"<i>{converter.audio_to_text()}</i>"
    del converter
    await bot.send_chat_action(message.chat.id, ChatActions.TYPING)
    await asyncio.sleep(3)
    await bot.send_message(message.chat.id, message_text,
                           reply_to_message_id=message.message_id)

# video download


@dp.callback_query_handler(text='download_mp4')
@dp.async_task
async def inline_keyboard_mp4(call: types.CallbackQuery):
    loading = "<i>Жүктеу | Loading</i>"
    await call.message.edit_text(text=loading)
    chat_id = call.message.chat.id
    service = "twitch.tv"
    if link.find(service) != -1:
        print("downloading with 720p")
        anotheroptions = {
            'format': 'mp4[height<=720]',
            'skip-download': True,
            'noplaylist': True,
            'outtmpl': 'video/%(title)s.%(ext)s',
            'cookies-from-browser': 'chrome',
        }
        try:
            with ytd.YoutubeDL(anotheroptions) as ytdl:
                start = datetime.now()
                ytdl.download([link])
                end = datetime.now()

        except:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(text='❌ Жабу | Close',
                                     callback_data='close'),
            )
            await bot.delete_message(call.message.chat.id, call.message.message_id)
            error = f'<i>Жүктеу кезінде қате орын алды\nError while loading content</i>\n\nContact: @damirtag'
            await bot.send_message(text=error, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
    else:
        print("downloading with 1080p")
        options = {'skip-download': True,
                   'format': 'mp4',
                   'outtmpl': 'video/%(id)s.%(ext)s',
                   'cookies-from-browser': 'chrome',
                   'cookies': 'cookies.txt',
                   'noplaylist': True,
                   }
        try:
            with ytd.YoutubeDL(options) as ytdl:
                start = datetime.now()
                ytdl.download([link])
                end = datetime.now()
        except ValueError:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(text='❌ Жабу | Close',
                                     callback_data='close'),
            )
            await bot.delete_message(call.message.chat.id, call.message.message_id)
            error = f'<i>Жүктеу кезінде қате орын алды\nError while loading content</i>\n\nContact: @damirtag'
            await bot.send_message(text=error, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
    result = ytdl.extract_info("{}".format(link))
    title = ytdl.prepare_filename(result)
    video_title = result.get('title', None)
    video = open(f'{title}', 'rb')
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    await bot.send_chat_action(call.message.chat.id, ChatActions.UPLOAD_VIDEO)
    await asyncio.sleep(3)
    loadtime = (end - start).total_seconds() * 1**1
    caption = f"Title: <a href='{link}'>{video_title}</a>\n<i>Loading time: {loadtime:.01f}sec</i>"
    await bot.send_video(chat_id=chat_id, video=video, caption=caption, reply_to_message_id=message_id)
    os.remove(title)
    print("%s has been removed successfuly" % title)


# audio section here mp3/soundcloud/spotify
# audio download


@dp.callback_query_handler(text='download_mp3')
@dp.async_task
async def inline_keyboard_mp3(call: types.CallbackQuery):
    print("downloading mp3 format")
    loading = "<i>Жүктеу | Loading</i>"
    await call.message.edit_text(text=loading)
    chat_id = call.message.chat.id
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
            start = datetime.now()
            ytdl.download([link])
            end = datetime.now()
    except:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text='❌ Жабу | Close',
                                 callback_data='close'),
        )
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        error = f'<i>Жүктеу кезінде қате орын алды\nError while downloading content</i>\n\nContact: @damirtag'
        await bot.send_message(text=error, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
    result = ytdl.extract_info("{}".format(link))
    title = ytdl.prepare_filename(result)
    video_title = result.get('title', None)
    delete = (f'{title}.mp3')
    audio = open(f'{title}.mp3', 'rb')
    loadtime = (end - start).total_seconds() * 1**1
    caption = f"Title: <a href='{link}'>{video_title}</a>\n<i>Loading time: {loadtime:.01f}sec</i>"
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    await bot.send_chat_action(call.message.chat.id, ChatActions.UPLOAD_AUDIO)
    await asyncio.sleep(3)
    await bot.send_audio(chat_id=chat_id, audio=audio, caption=caption, reply_to_message_id=message_id)
    # deleting file after
    os.remove(delete)
    print("%s has been removed successfuly" % title)
# soundcloud track install


@dp.message_handler(regexp='(?:https?://)?(?:www\.)?(?:soundcloud\.com)')
@dp.async_task
async def soundload(message: types.Message):
    link = message.text
    current_date = datetime.now(pytz.timezone('Asia/Almaty'))
    if current_date.tzinfo == None or current_date.\
            tzinfo.utcoffset(current_date) == None:
        print("Unaware")
    else:
        print("======")
    username = message.from_user.first_name
    msg = message.text
    print(f"[{current_date}] {username} : {msg}")
    print("downloading mp3 format | SOUNDCLOUD")
    options = {
        'skip-download': True,
        'writethumbnail': True,
        'embedthumbnail': True,
        'noplaylist': True,
        'format': 'bestaudio/best',
        'outtmpl': 'audio/%(title)s',
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
            start = datetime.now()
            ytdl.download([link])
            end = datetime.now()
    except:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text='❌ Жабу | Close',
                                 callback_data='close'),
        )
        chat_id = message.chat.id
        error = f'<i>Жүктеу кезінде қате орын алды\nError while downloading content</i>\n\nContact: @damirtag'
        return await bot.send_message(text=error, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
    result = ytdl.extract_info("{}".format(link))
    title = ytdl.prepare_filename(result)
    delete = (f'{title}.mp3')
    audio = open(f'{title}.mp3', 'rb')
    loadtime = (end - start).total_seconds() * 1**1
    none = "Damir the best"
    video_title = result.get('title', none)
    # user = result.get('user', none)
    # artist = result.get('artist', none)
    # album = result.get('album', none)
    username = message.from_user.username
    caption = f"<b>Title:</b> <a href='{link}'>{video_title}</a>\n<i>Loading time: {loadtime:.01f}sec</i>"
    chat_id = message.chat.id
    message_id = message.message_id
    await bot.send_chat_action(message.chat.id, ChatActions.UPLOAD_AUDIO)
    await asyncio.sleep(3)
    await bot.send_audio(chat_id=chat_id, audio=audio, caption=caption, reply_to_message_id=message_id)
    # deleting file after
    os.remove(delete)
    print("%s has been removed successfuly" % title)


@dp.message_handler(regexp='(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be|tiktok\.com|instagram\.com/reel/|pinterest.com|twitch\.tv/)')
@dp.async_task
async def downloading(message: types.Message):
    current_date = datetime.now(pytz.timezone('Asia/Almaty'))
    if current_date.tzinfo == None or current_date.\
            tzinfo.utcoffset(current_date) == None:
        print("Unaware")
    else:
        print("======")
    username = message.from_user.first_name
    msg = message.text
    print(f"[{current_date}] {username} : {msg}")
    global link
    link = message.text
    global message_id
    message_id = message.message_id
    # messages texts
    text = "Қандай пішінде жүктеп алу керек?\nIn what type to download?"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(text='📹', callback_data='download_mp4'),
        InlineKeyboardButton(text='🔊', callback_data='download_mp3'),
        # InlineKeyboardButton(text='Image (TikTok)',
        #                      callback_data='download_img'),
    )
    await asyncio.sleep(0.1)
    return await message.reply(text=text, reply_markup=keyboard)

if __name__ == '__main__':
    logger.info("Starting bot")
    executor.start_polling(dp, skip_updates=True)
