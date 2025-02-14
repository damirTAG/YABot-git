import aiohttp, re
from dataclasses import dataclass
from functools import wraps
from aiogram import types
import sqlite3


class SoundCloudSearchException(Exception):
    pass

class Tools():
    def __init__(self) -> None:
        """
        HEADERS NOT WORKING, SO NOT USING NEED TO CHANGE
        """
        # self.headers = {
        #     'User-Agent': 'Mozilla/5.0 (iPad; U; CPU OS 3_2 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) '
        #                 'Version/4.0.4 Mobile/7B334b Safari/531.21.102011-10-16 20:23:10'
        # }
        pass

    async def convert_share_urls(self, url: str):
        print('converting link...')
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=False) as response:
                    location = response.headers.get('Location', '')
                    print(f"Location: {location}")

                    soundcloud_match = re.search(r'(https://soundcloud\.com/[\w-]+/[\w-]+)', location)
                    youtube_match = re.search(r'(https://www\.youtube\.com/watch\?v=[\w-]+)', location)
                    instagram_match = re.search(r'(https://www\.instagram\.com/(p|reel|reels|tv)/[\w-]+)/?', url)
                    
                    if soundcloud_match:
                        url = soundcloud_match.group(1)
                    elif youtube_match:
                        url = youtube_match.group(1)
                    elif instagram_match:
                        url = instagram_match.group(1)
                        
                    print('obtaining the original link successfully, the original link is: {}'.format(url))
                    return url
        except Exception as e:
            print('could not get original link!')
            print(e)
            return None

    @staticmethod
    def log(command_name):
        def decorator(handler):
            @wraps(handler)
            async def wrapper(message: types.Message, *args, **kwargs):
                user_id = message.from_user.id
                username = message.from_user.username
                first_name = message.from_user.first_name
                last_name = message.from_user.last_name

                conn = sqlite3.connect("stats.db")
                cursor = conn.cursor()

                # Добавляем пользователя, если его нет
                cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)", 
                            (user_id, username, first_name, last_name))

                # Логируем команду
                cursor.execute("INSERT INTO commands (user_id, command) VALUES (?, ?)", (user_id, command_name))
                
                conn.commit()
                conn.close()

                return await handler(message, *args, **kwargs)
            return wrapper
        return decorator

@dataclass
class ConsoleColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def init_db():
    conn = sqlite3.connect("stats.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            command TEXT,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    conn.commit()
