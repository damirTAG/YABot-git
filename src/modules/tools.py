import aiohttp, re
import sqlite3, config
from typing import Tuple, Optional
from dataclasses import dataclass
from functools import wraps

OPENAI_API_KEY = config.OPEN_AI_TOKEN
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
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
            async def wrapper(message, *args, **kwargs):
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
    
    @staticmethod
    def parse_currency_query(text: str) -> Optional[Tuple[float, str, str]]:
        """Parse message text into amount, from_currency, and to_currency"""
        # Remove extra spaces and convert to lowercase
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
    
    @staticmethod
    async def generate_response(prompt: str) -> str:
        """
        Generate response from ChatGPT API
        """
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты встроен в Ержан бота в Телеграме. Отвечай на вопросы юзеров, шути/подкалывай "
                            "Можно обращаться на 'ты'. Будь иногда дерзким "
                            "В ответах с кодом можно слегка токсичить. Если встречаешь вопросы по типу "
                            "'кто такой сын миража', то напридумай какую нибудь абсурдную историю. "
                            "Поддерживай многоязычность, отвечай на том языке на котором задан вопрос"
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "max_tokens": 300  # Ограничение длины ответа
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(OPENAI_API_URL, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content'].strip()
                    else:
                        return None
        except Exception as e:
            print(f"[chatgpt] Error generating response: {e}")
            return "An error occurred while processing your request."

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
