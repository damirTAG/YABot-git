import aiohttp, re
import asyncio
from dataclasses import dataclass

class Tools:
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