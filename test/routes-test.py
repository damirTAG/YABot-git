import yt_dlp
import asyncio
import aiohttp
from typing import Optional


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
            
            if 'entries' in info:
                for entry in info['entries']:
                    id = entry['id']
                    title = entry['title']
                    uploader = entry['uploader']
                    url = entry['url']
                    print(f"[Soundcloud] Downloading: {title}...")
                    data = {
                        'id': id,
                        'title': title,
                        'uploader': uploader,
                        'url': url
                    }
                    return data
                    
            else:
                print("No tracks found.")
                return None

    async def async_download(self, id: Optional[int] = None, url: Optional[str] = None) -> None:
        data = await self.search()

        if data:
            url = url if url is not None else data['url']
            id = id if id is not None else data['id']

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as sound_resp:
                    if sound_resp.status == 200:
                        sound_filename = f"{id}.mp3"
                        with open(sound_filename, 'wb') as f:
                            f.write(await sound_resp.read())
                        print(f"[Soundcloud] Downloaded: {sound_filename}")
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as sound_resp:
                    if sound_resp.status == 200:
                        sound_filename = f"{id}.mp3"
                        with open(sound_filename, 'wb') as f:
                            f.write(await sound_resp.read())
                        print(f"[Soundcloud] Downloaded: {sound_filename}")


async def main():
    downloader = SoundCloudDownloader("rallyhouse")
    await downloader.async_download()

if __name__ == "__main__":
    asyncio.run(main())
