import re, logging

from dataclasses        import dataclass
from aiogram            import types, filters
from typing             import Tuple, Optional

import aiohttp

logger = logging.getLogger()

class Tools():
    def __init__(self) -> None:
        self.PLATFORM_PATTERNS = {
            "TikTok": r"(?:https?://)?(?:www\.)?tiktok\.com",
            "SoundCloud": r"(?:https?://)?(?:www\.)?soundcloud\.com",
            "Instagram": r"(?:https?://)?(?:www\.)?instagram\.com",
            "YouTube": r"(?:https?://)?(?:www\.)?(youtube\.com|youtu\.be)"
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

    def check_query(self, query, max_words=7):
        words = query.split()
        if len(words) > max_words:
            return False

    def parse_platforms(self, video_links):
        try:
            platform_counts = {
                "TikTok": 0, 
                "SoundCloud": 0, 
                "Instagram": 0, 
                "Yandex Music": 0,
                "YouTube": 0
            }
        
            for link in video_links:
                if link.isdigit():  # Yandex Music хранит ID, а не ссылки
                    platform_counts["Yandex Music"] += 1
                else:
                    for platform, pattern in self.PLATFORM_PATTERNS.items():
                        if re.search(pattern, link):
                            platform_counts[platform] += 1
                            break
            
            return platform_counts
        except Exception as e:
            logger.error(f'Error in parse_platforms: {e}')


class YANDEX_MUSIC_TRACK_CAPTION:
    def __init__(self, track):
        self.track = track

    def format(self) -> str:
        artist_label = "👤 Artist:" if "," not in self.track.artists else "👥 Artists:"
        
        return (
            f"<b>🎵 Track:</b> <a href='https://music.yandex.com/album/{self.track.album_id}/track/{self.track.id}'>"
            f"{self.track.title}</a> • {self.track.year}\n"
            f"<b>{artist_label}</b> <i>{self.track.artists}</i>\n"
            f"<b>📀 Album:</b> <a href='https://music.yandex.com/album/{self.track.album_id}'>"
            f"{self.track.album_title}</a>\n"
            f"<b>🎶 Genre:</b> <i>{self.track.genre.capitalize()}</i>\n"
            f"<b>⏱️ Duration:</b> <code>{int(self.track.duration // 60)}:{int(self.track.duration % 60):02d}</code>"
        )


class RegexFilter(filters.BaseFilter):
    def __init__(self, pattern):
        self.pattern = pattern
        
    async def __call__(self, message: types.Message):
        if not message.text:
            return False
        return bool(re.search(self.pattern, message.text))

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