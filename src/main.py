from config import TOKEN
import os
from datetime import datetime
import yt_dlp as ytd
from aiogram import Dispatcher, Bot, executor, types
from aiogram import asyncio
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatActions
from aiogram.dispatcher.filters import Text
# =========
storage = MemoryStorage()
bot = Bot(TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=storage)
# =========


@dp.message_handler(commands='start')
async def hello(message: types.Message):
    # Обычные кнопки
    start_button = ['Установить/Download']
    keyboards = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboards.add(*start_button)

    await message.reply("🏴󠁧󠁢󠁥󠁮󠁧󠁿󠁧󠁢󠁥󠁮󠁧󠁿 Hello there! This is YouTube/TikTok/Reels video and audio bot installer\nJust send me a link to install!\n\n🇷🇺 Привет! Это бот который устанавливает видео и аудио с Ютуба, ТикТока и Риллсов,\nПросто скинь мне ссылку!")


# video download
@dp.callback_query_handler(text='download_mp4')
async def inline_keyboard_mp4(call: types.CallbackQuery):
    try:
        loading = "<i>Загружаю | Loading</i>"
        await call.message.edit_text(text=loading)
        chat_id = call.message.chat.id
        options = {'skip-download': True,
                   'format': 'mp4',
                   'outtmpl': 'video/%(title)s.%(ext)s',
                   'cookies-from-browser': 'chrome',
                   }

        with ytd.YoutubeDL(options) as ytdl:
            start = datetime.now()
            ytdl.download([link])
            result = ytdl.extract_info("{}".format(link))
            title = ytdl.prepare_filename(result)
            video = open(f'{title}', 'rb')
            end = datetime.now()
            await bot.delete_message(call.message.chat.id, call.message.message_id)
            await bot.send_chat_action(call.message.chat.id, ChatActions.UPLOAD_VIDEO)
            await asyncio.sleep(3)
            loadtime = (end - start).total_seconds() * 1**1
            caption = f"<a href='{link}'>Ссылка | Link</a>\n<i>Loading time: {loadtime:.01f}sec</i>"
            await bot.send_video(chat_id=chat_id, video=video, caption=caption, reply_to_message_id=message_id)
            os.remove(title)
            print("%s has been removed successfuly" % title)
    except:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text='❌ Close | Закрыть',
                                 callback_data='close'),
        )
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        error = f'<i>Произошла ошибка при загрузке.\nError while downloading content</i>\n\nContact: @damirtag'
        await bot.send_message(text=error, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
        print(error)

# audio download


@dp.callback_query_handler(text='download_mp3')
async def inline_keyboard_mp3(call: types.CallbackQuery):
    try:
        loading = "<i>Загружаю | Loading</i>"
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
            delete = (f'{title}.mp3')
            audio = open(f'{title}.mp3', 'rb')
            end = datetime.now()
            loadtime = (end - start).total_seconds() * 1**1
            caption = f"<a href='{link}'>Ссылка | Link</a>\n<i>Loading time: {loadtime:.01f}sec</i>"
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
            InlineKeyboardButton(text='❌ Close | Закрыть',
                                 callback_data='close'),
        )
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        error = f'<i>Произошла ошибка при загрузке.\nError while downloading content</i>\n\nContact: @damirtag'
        await bot.send_message(text=error, chat_id=chat_id, reply_to_message_id=message_id, reply_markup=keyboard)
        print(error)


# Установить
@dp.message_handler(Text(equals='Установить/Download'))
async def start_dw(message: types.Message):
    await message.reply('Скинь ссылку!/Send me a link!')


@dp.message_handler(regexp='(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be|tiktok\.com|instagram\.com/reel/|pinterest.com)')
async def downloading(message: types.Message):
    global link
    link = message.text
    global message_id
    message_id = message.message_id
    # messages texts

    text = "В каком виде скачать?\nIn what type to download?"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(text='Видео/Video', callback_data='download_mp4'),
        InlineKeyboardButton(text='Аудио/Audio', callback_data='download_mp3'),
        # InlineKeyboardButton(text='Image (TikTok)',
        #                      callback_data='download_img'),
    )
    await message.reply(text=text, reply_markup=keyboard)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
