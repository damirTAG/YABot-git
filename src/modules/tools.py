import aiohttp, re
import asyncio
import yt_dlp

from dataclasses import dataclass
from typing import Optional

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
        

class SoundCloudDownloader:
    def __init__(self, query: str):
        self.query = query

    async def search(self):
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f'scsearch:{self.query}'
            info = ydl.extract_info(search_query, download=False)
            print(f'[Soundcloud:search] Searching for {self.query}')
            
            if 'entries' in info and info['entries']:
                entry = info['entries'][0]
                id = entry['id']
                title = entry['title']
                uploader = entry['uploader']
                url = entry['url']
                webpage = entry['webpage_url']
                print(f"[Soundcloud] Data fetched: {title}...")
                data = {
                    'id': id,
                    'title': title,
                    'uploader': uploader,
                    'url': url,
                    'webpage': webpage
                }
                return data
            else:
                print("No tracks found.")
                raise SoundCloudSearchException("Track not found")

    async def async_download(self, id: Optional[int] = None, url: Optional[str] = None) -> None:
        if id is None and url is None:
            data = await self.search()
            url = data['url']
            id = data['id']
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as sound_resp:
                    if sound_resp.status == 200:
                        sound_filename = f"{id}.mp3"
                        with open(sound_filename, 'wb') as f:
                            f.write(await sound_resp.read())

                        print(f"[Soundcloud] Downloaded: {sound_filename}")
                        return sound_filename
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as sound_resp:
                    if sound_resp.status == 200:
                        sound_filename = f"{id}.mp3"
                        with open(sound_filename, 'wb') as f:
                            f.write(await sound_resp.read())

                        print(f"[Soundcloud] Downloaded: {sound_filename}")
                        return sound_filename

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

@dataclass
class Platforms:
    Tiktok = 'TikTok'
    Instagram = 'Instagram'
    Youtube = 'YouTube'
    Soundcloud = 'Soundcloud'
    Twitch = 'Twitch'
    VK = 'VK'

if __name__ == '__main__':
    tools = Tools()
    asyncio.run(tools.convert_share_urls(url='https://youtu.be/SlqpzGyAFoU'))
    #asyncio.run(tools.convert_share_urls(url='https://on.soundcloud.com/PpAok'))
    #asyncio.run(tools.convert_share_urls(url='https://www.instagram.com/reel/C4GNIoXiyG-/?igsh=bzlxYXJuczFyMnRo'))