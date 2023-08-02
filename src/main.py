from config import TOKEN
import os
from datetime import datetime
import pytz
import yt_dlp as ytd
from aiogram import Dispatcher, Bot, executor, types
from aiogram import asyncio
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatActions
from aiogram.dispatcher.filters import Text
# import requests
# from bs4 import BeautifulSoup
# =========
storage = MemoryStorage()
bot = Bot(TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=storage)
# =========


@dp.message_handler(commands='start')
async def hello(message: types.Message):
    start = "🏴󠁧󠁢󠁥󠁮󠁧󠁿󠁧󠁢󠁥󠁮󠁧󠁿 Hello there! This is YouTube/TikTok/Reels video and audio bot installer\n🇰🇿 Сәлем! Бұл YouTube/TikTok/Reels/Twitch Clips/SoundcloudTracks бот орнатушысы"

    await message.reply(text=start)


# CLOSE BUTTON
@dp.callback_query_handler(text="close")
async def close(call: types.CallbackQuery):
    await bot.delete_message(call.message.chat.id, call.message.message_id)

# video download


@dp.callback_query_handler(text='download_mp4')
async def inline_keyboard_mp4(call: types.CallbackQuery):
    loading = "<i>Жүктеу | Loading</i>"
    await call.message.edit_text(text=loading)
    chat_id = call.message.chat.id
    try:
        service = "twitch.tv"
        if link.find(service) != -1:
            print("downloading with 720p")
            anotheroptions = {
                'format': 'mp4[height<=720]',
                'skip-download': True,
                'outtmpl': 'video/%(title)s.%(ext)s',
                'cookies-from-browser': 'chrome',
            }
            with ytd.YoutubeDL(anotheroptions) as ytdl:
                start = datetime.now()
                ytdl.download([link])
                result = ytdl.extract_info("{}".format(link))
                title = ytdl.prepare_filename(result)
                video_title = result.get('title', None)
                video = open(f'{title}', 'rb')
                end = datetime.now()
                await bot.delete_message(call.message.chat.id, call.message.message_id)
                await bot.send_chat_action(call.message.chat.id, ChatActions.UPLOAD_VIDEO)
                await asyncio.sleep(3)
                loadtime = (end - start).total_seconds() * 1**1
                caption = f"Title: <a href='{link}'>{video_title}</a>\n<i>Loading time: {loadtime:.01f}sec</i>"
                await bot.send_video(chat_id=chat_id, video=video, caption=caption, reply_to_message_id=message_id)
                os.remove(title)
                print("%s has been removed successfuly" % title)
        else:
            print("downloading with 1080p")
            options = {'skip-download': True,
                       'format': 'mp4',
                       'outtmpl': 'video/%(title)s.%(ext)s',
                       'cookies-from-browser': 'chrome',
                       'cookies': 'cookies.txt',
                       }
            with ytd.YoutubeDL(options) as ytdl:
                start = datetime.now()
                ytdl.download([link])
                result = ytdl.extract_info("{}".format(link))
                title = ytdl.prepare_filename(result)
                video_title = result.get('title', None)
                video = open(f'{title}', 'rb')
                end = datetime.now()
                await bot.delete_message(call.message.chat.id, call.message.message_id)
                await bot.send_chat_action(call.message.chat.id, ChatActions.UPLOAD_VIDEO)
                await asyncio.sleep(3)
                loadtime = (end - start).total_seconds() * 1**1
                caption = f"Title: <a href='{link}'>{video_title}</a>\n<i>Loading time: {loadtime:.01f}sec</i>"
                await bot.send_video(chat_id=chat_id, video=video, caption=caption, reply_to_message_id=message_id)
                os.remove(title)
                print("%s has been removed successfuly" % title)
    except:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text='❌ Жабу | Close',
                                 callback_data='close'),
        )
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        error = f'<i>Жүктеу кезінде қате орын алды\nError while loading content</i>\n\nContact: @damirtag'
        await bot.send_message(text=error, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)


# audio download


@dp.callback_query_handler(text='download_mp3')
async def inline_keyboard_mp3(call: types.CallbackQuery):
    try:
        print("downloading mp3 format")
        loading = "<i>Жүктеу | Loading</i>"
        await call.message.edit_text(text=loading)
        chat_id = call.message.chat.id
        options = {
            'skip-download': True,
            'format': 'bestaudio/best',
            'outtmpl': 'audio/%(title)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'cookies-from-browser': 'chrome',
        }

        with ytd.YoutubeDL(options) as ytdl:
            start = datetime.now()
            ytdl.download([link])
            result = ytdl.extract_info("{}".format(link))
            title = ytdl.prepare_filename(result)
            video_title = result.get('title', None)
            delete = (f'{title}.mp3')
            audio = open(f'{title}.mp3', 'rb')
            end = datetime.now()
            loadtime = (end - start).total_seconds() * 1**1
            caption = f"Title: <a href='{link}'>{video_title}</a>\n<i>Loading time: {loadtime:.01f}sec</i>"
            await bot.delete_message(call.message.chat.id, call.message.message_id)
            await bot.send_chat_action(call.message.chat.id, ChatActions.UPLOAD_AUDIO)
            await asyncio.sleep(3)
            await bot.send_audio(chat_id=chat_id, audio=audio, caption=caption, reply_to_message_id=message_id)
            # deleting file after
            os.remove(delete)
            print("%s has been removed successfuly" % title)
    except:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text='❌ Жабу | Close',
                                 callback_data='close'),
        )
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        error = f'<i>Жүктеу кезінде қате орын алды\nError while downloading content</i>\n\nContact: @damirtag'
        await bot.send_message(text=error, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)


@dp.message_handler(regexp='(?:https?://)?(?:www\.)?(?:soundcloud\.com)')
async def soundload(message: types.Message):
    link = message.text
    current_date = datetime.now(pytz.timezone('Asia/Almaty'))
    if current_date.tzinfo == None or current_date.\
            tzinfo.utcoffset(current_date) == None:
        print("Unaware")
    else:
        print("=== BOT ACTION NOTICED ===")
    username = message.from_user.first_name
    msg = message.text
    print(f"[{current_date}] {username} : {msg}")
    try:
        print("downloading mp3 format | SOUNDCLOUD")
        options = {
            'skip-download': True,
            'writethumbnail': True,
            'embedthumbnail': True,
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
            'cookies-from-browser': 'chrome',
        }
        with ytd.YoutubeDL(options) as ytdl:
            start = datetime.now()
            ytdl.download([link])
            end = datetime.now()

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
        caption = f"<b>Title:</b> <a href='{link}'>{video_title}</a>\n<i>Loading time: {loadtime:.01f}sec</i>"
        chat_id = message.chat.id
        message_id = message.message_id
        await bot.send_chat_action(message.chat.id, ChatActions.UPLOAD_AUDIO)
        await asyncio.sleep(3)
        await bot.send_audio(chat_id=chat_id, audio=audio, caption=caption, reply_to_message_id=message_id)
        # deleting file after
        os.remove(delete)
        print("%s has been removed successfuly" % title)
    except ValueError:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text='❌ Жабу | Close',
                                 callback_data='close'),
        )
        chat_id = message.chat.id
        error = f'<i>Жүктеу кезінде қате орын алды\nError while downloading content</i>\n\nContact: @damirtag'
        await bot.send_message(text=error, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)


@dp.message_handler(regexp='(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be|tiktok\.com|instagram\.com/reel/|pinterest.com|twitch\.tv/)')
async def downloading(message: types.Message):
    current_date = datetime.now(pytz.timezone('Asia/Almaty'))
    if current_date.tzinfo == None or current_date.\
            tzinfo.utcoffset(current_date) == None:
        print("Unaware")
    else:
        print("=== BOT ACTION NOTICED ===")
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
    await message.reply(text=text, reply_markup=keyboard)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, fast=True)
