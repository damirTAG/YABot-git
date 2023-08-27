from config import TOKEN

# TEXT FILES IMPORT BEGIN
from allText import start_txt, text_txt, error_txt, help_txt
# TEXT FILES IMPORT END

import os
import logging
from random import randrange
from convert import Converter
from datetime import datetime
import pytz
import yt_dlp as ytd
from aiogram import Dispatcher, Bot, executor, types
from aiogram import asyncio
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatActions
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
    start = start_txt
    await message.reply(text=start)


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
        nowords = "<i>Речь не распознана</i>"
        await bot.send_message(message.chat.id, text=nowords,
                               reply_to_message_id=message.message_id)

# video download


@dp.callback_query_handler(text='download_mp4')
@dp.async_task
async def inline_keyboard_mp4(call: types.CallbackQuery):
    loading = "<i>Жүктеу | Loading</i>"
    await call.message.edit_text(text=loading)
    chat_id = call.message.chat.id
    print("downloading with 1080p")
    options = {'skip-download': True,
               'format': 'mp4',
               'outtmpl': 'video/%(title)s.%(ext)s',
               'cookies-from-browser': 'chrome',
               'cookies': 'cookies.txt',
               'noplaylist': True,
               }
    try:
        with ytd.YoutubeDL(options) as ytdl:
            result = ytdl.extract_info("{}".format(link))
            title = ytdl.prepare_filename(result)
            start = datetime.now()
            ytdl.download([link])
            end = datetime.now()
    except:
        print(ValueError)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text='❌ Жабу | Close',
                                 callback_data='close'),
        )
        await bot.delete_message(call.message.chat.id, call.message.message_id)

        await bot.send_message(text=error_txt, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)

    video_title = result.get('title', None)
    video = open(f'{title}', 'rb')
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    loadtime = (end - start).total_seconds() * 1**1
    caption = f"Title: <a href='{link}'>{video_title}</a>\n<i>Loading time: {loadtime:.01f}sec</i>"
    try:
        return await bot.send_video(chat_id=chat_id, video=video, caption=caption, reply_to_message_id=message_id)
    except:
        print(ValueError)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text='❌ Жабу | Close',
                                 callback_data='close'),
        )
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        return await bot.send_message(text=error_txt, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
    finally:
        # deleting file after
        os.remove(title)
        print("%s has been removed successfuly" % title)

# if not youtube download


@dp.message_handler(regexp='(?:https?://)?(?:www\.)?(?:vk\.com/clip|tiktok\.com|instagram\.com/reel/|instagram\.com/stories/|twitch\.tv/)')
@dp.async_task
async def loadvideo(message: types.Message):
    await bot.send_chat_action(message.chat.id, ChatActions.RECORD_VIDEO)
    options = {'skip-download': True,
               'format': 'mp4',
               'outtmpl': 'video/%(title)s.%(ext)s',
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

    except ValueError:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text='❌ Жабу | Close',
                                 callback_data='close'),
        )
        await bot.send_message(text=error_txt, chat_id=message.chat.id, reply_to_message_id=message_id, reply_markup=keyboard)
    video_title = result.get('title', None)
    video = open(f'{title}', 'rb')
    caption = f"<b>Title: <a href='{link}'>{video_title}</a></b>"
    try:
        return await bot.send_video(chat_id=message.chat.id, video=video, caption=caption, reply_to_message_id=message_id)
    except ValueError:
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


# audio section here mp3/soundcloud
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
    await bot.send_chat_action(message.chat.id, ChatActions.RECORD_AUDIO)
    link = message.text
    current_date = datetime.now(pytz.timezone('Asia/Almaty'))
    if current_date.tzinfo == None or current_date.\
            tzinfo.utcoffset(current_date) == None:
        print("Unaware")
    else:
        print("======")
    username = message.from_user.full_name
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
            # start = datetime.now()
            ytdl.download([link])
            # end = datetime.now()
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
    # loadtime = (end - start).total_seconds() * 1**1
    none = "Damir the best"
    video_title = result.get('title', none)
    uploader = result.get('uploader', none)
    uploader_id = result.get('uploader_id', none)
    uploader_link = f'https://soundcloud.com/user-{uploader_id}'
    username = message.from_user.username
    caption = f'<a href="{link}">{video_title}</a> — <a href="{uploader_link}">{uploader}</a>'
    chat_id = message.chat.id
    message_id = message.message_id
    try:
        await bot.send_chat_action(message.chat.id, ChatActions.UPLOAD_AUDIO)
        return await bot.send_audio(chat_id=chat_id, audio=audio, caption=caption, reply_to_message_id=message_id)
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


@dp.message_handler(regexp='(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)')
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
    global link
    link = message.text
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

if __name__ == '__main__':
    logger.info("Starting bot")
    executor.start_polling(dp, skip_updates=True)
