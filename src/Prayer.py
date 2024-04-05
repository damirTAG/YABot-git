import aiohttp
import asyncio
import logging
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram import Bot
from datetime import datetime, timedelta, timezone
from database import Database
from tenacity import retry, stop_after_attempt, wait_fixed

db = Database('database/prayer_times.db')

UPDATE_INTERVAL = 60
MAX_RETRIES = 3
RETRY_INTERVAL = 5

class PrayerCheck:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.today = datetime.now(timezone.utc) + timedelta(hours=5)
        self.formatted_date = self.today.strftime('%d-%m-%Y')
        self.base_url = 'http://api.aladhan.com/v1/timingsByCity'
        self.method_params = 'method=8&tune=19,28,-3,3,58,3,3,-9,0'
        self.loop = asyncio.get_event_loop()

    @retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_fixed(RETRY_INTERVAL))
    async def fetch_prayer_times(self, city: str) -> dict:
        formatted_date = self.today.strftime('%d-%m-%Y')
        url = f'https://api.aladhan.com/v1/timingsByCity/{formatted_date}?city={city}&country=Kazakhstan&method=8&tune=19,28,-3,3,58,3,3,-9,0'

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()
                    timings = {k: v for k, v in data.get('data', {}).get('timings', {}).items() if k not in ['Imsak', 'Firstthird', 'Lastthird']}
                    return timings
        except aiohttp.ClientConnectorError:
            logging.warning(f"Failed to connect to {url}. Retrying...")
            raise
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            raise

    async def check_prayer_times(self):
        data = db.get_pray_data()
        
        for user_id, city in data:
            timings = await self.fetch_prayer_times(city)
                
            for prayer, time in timings.items():
                await asyncio.sleep(1)

                current_time = datetime.now(timezone.utc) + timedelta(hours=5)
                formatted_current_time = datetime.strptime(current_time.strftime('%H:%M'), '%H:%M')
                prayer_time = datetime.strptime(time, '%H:%M')

                if formatted_current_time == prayer_time:
                    if prayer in ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']:
                        keyboard = InlineKeyboardMarkup()
                        keyboard.add(
                            InlineKeyboardButton(text='❌🤲', callback_data='toRead'),
                        )
                        await self.bot.send_message(user_id, f"<b>{prayer} · {time}</b>", reply_markup=keyboard)
                    else:
                        await self.bot.send_message(user_id, f"<b>{prayer} · {time}</b>")



    async def run(self):
        while True:
            await self.check_prayer_times()
            await asyncio.sleep(UPDATE_INTERVAL)

async def init(bot):
    prayer_check = PrayerCheck(bot)
    asyncio.create_task(prayer_check.run())
