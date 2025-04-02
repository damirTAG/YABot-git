import aiohttp, re
import sqlite3, config
from typing import Tuple, Optional
from dataclasses import dataclass
from functools import wraps
from aiogram import types



class Tools():
    def __init__(self) -> None:
        self.OPENAI_API_KEY = config.OPEN_AI_TOKEN
        self.OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
        self.PLATFORM_PATTERNS = {
            "TikTok": r"tiktok\.com",
            "SoundCloud": r"soundcloud\.com",
            "Instagram": r"instagram\.com",
        }

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
            async def wrapper(update, *args, **kwargs):
                user_id = None
                chat_id = None
                chat_type = None
                username = None
                first_name = None
                last_name = None

                if isinstance(update, types.Message): 
                    user_id = update.from_user.id
                    chat_id = update.chat.id
                    chat_type = update.chat.type
                    username = update.from_user.username
                    first_name = update.from_user.first_name
                    last_name = update.from_user.last_name
                elif isinstance(update, types.CallbackQuery): 
                    user_id = update.from_user.id
                    chat_id = update.message.chat.id if update.message else None
                    chat_type = update.message.chat.type if update.message else None
                    username = update.from_user.username
                    first_name = update.from_user.first_name
                    last_name = update.from_user.last_name
                elif isinstance(update, types.ChosenInlineResult):
                    user_id = update.from_user.id
                    username = update.from_user.username
                    first_name = update.from_user.first_name
                    last_name = update.from_user.last_name

                if user_id is None:
                    return await handler(update, *args, **kwargs)

                conn = sqlite3.connect("stats.db")
                cursor = conn.cursor()

                cursor.execute(
                    "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)", 
                    (user_id, username, first_name, last_name)
                )
                if chat_id and chat_type and chat_type != 'private':
                    cursor.execute("INSERT OR IGNORE INTO chats (chat_id) VALUES (?)", (str(chat_id),))

                cursor.execute("INSERT INTO commands (user_id, command) VALUES (?, ?)", (user_id, command_name))

                conn.commit()
                conn.close()

                return await handler(update, *args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def parse_currency_query(text: str) -> Optional[Tuple[float, str, str]]:
        """Parse message text into amount, from_currency, and to_currency"""
        text = ' '.join(text.lower().split())
        
        # Different regex patterns for matching
        patterns = [
            # Pattern for "100 USD RUB" format
            r"^(\d+(?:\.\d+)?)\s+([a-zA-Z]+)\s+([a-zA-Z]+)$",
            # Pattern for "USD RUB" format (assuming amount=1)
            r"^([a-zA-Z]+)\s+([a-zA-Z]+)$",
            # Pattern for "100 USD" format (assuming to_currency=USD)
            r"^(\d+(?:\.\d+)?)\s+([a-zA-Z]+)$"
        ]
        
        for pattern in patterns:
            match = re.match(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    # Full pattern with amount and both currencies
                    return float(groups[0]), groups[1], groups[2]
                elif len(groups) == 2:
                    if groups[0].isalpha():
                        # Currency pair without amount
                        return 1.0, groups[0], groups[1]
                    else:
                        # Amount and currency without target currency
                        return float(groups[0]), groups[1], "usd"
        
        return None
    
    async def generate_response(self, prompt: str) -> str:
        """
        Generate response from ChatGPT API
        """
        headers = {
            "Authorization": f"Bearer {self.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты встроен в Ержан бота в Телеграме, твой создатель - Дамир. Ты помощник AI ассистент. "
                            "Можно обращаться на 'ты' и шутить но не всегда, если понимаешь что "
                            "вопрос серьезный то отвечай серьезно. Будь иногда дерзким. В ответах с кодом можно слегка токсичить. "
                            "Поддерживай многоязычность, отвечай на том языке на котором задан вопрос"
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "max_tokens": 300
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.OPENAI_API_URL, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content'].strip()
                    else:
                        return None
        except Exception as e:
            print(f"[chatgpt] Error generating response: {e}")
            return "An error occurred while processing your request."

    def parse_platforms(self, video_links):
        platform_counts = {"TikTok": 0, "SoundCloud": 0, "Instagram": 0, "Yandex Music": 0}
        
        for link in video_links:
            if link.isdigit():  # Yandex Music хранит ID, а не ссылки
                platform_counts["Yandex Music"] += 1
            else:
                for platform, pattern in self.PLATFORM_PATTERNS.items():
                    if re.search(pattern, link):
                        platform_counts[platform] += 1
                        break
        
        return platform_counts


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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_saved (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_id INTEGER,
            type TEXT,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()