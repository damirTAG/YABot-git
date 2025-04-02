import asyncio, aiohttp
import os
import yt_dlp
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from dataclasses import dataclass
from typing import List

PATTERN = r"(https://soundcloud\.com/[^/]+)"

@dataclass
class Track:
    track_id        : str   = None
    title           : str   = None
    artists         : str   = None
    duration        : int   = None  # Duration in seconds
    caption         : str   = None
    link            : str   = None
    download_link   : str   = None

class SoundCloudTool:
    YTDL_OPTS = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "default_search": "scsearch",
        "quiet": True,
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }
        ],
    }

    def __init__(self):
        self.ytdl = yt_dlp.YoutubeDL(self.YTDL_OPTS)

    async def search_tracks(self, query: str, count: int = 10) -> List[Track]:
        search_query = f"scsearch{count}:{query}"
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, self.ytdl.extract_info, search_query, False)
        
        tracks = []
        if "entries" in data:
            for entry in data["entries"]:
                if not entry:
                    continue
                track = self._track_instance(entry)
                tracks.append(track)
        
        return tracks

    async def get_track(self, track_url: str) -> Track:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, self.ytdl.extract_info, track_url, False)
        return self._track_instance(data)

    async def save_track(self, track: Track, output_folder: str = "audio") -> str:
        os.makedirs(output_folder, exist_ok=True)
        output_file = os.path.join(output_folder, f"track_{track.track_id}.mp3")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(track.download_link) as response:
                if response.status == 200:
                    with open(output_file, "wb") as f:
                        f.write(await response.read())
        
        self._insert_metadata(output_file, track.title, track.artists)
        return output_file

    @staticmethod
    def _insert_metadata(file_path: str, title: str, artist: str):
        audio = MP3(file_path, ID3=EasyID3)
        audio["title"] = title
        audio["artist"] = artist
        audio.save()

    @staticmethod
    def _get_download_link(entry: dict) -> str:
        formats: dict | None = entry.get("formats", [])
        # print(formats) # Debugging
        for fmt in formats:
            if (
                fmt.get("ext") == "mp3" 
                and fmt.get("format_id") == "http_mp3_1_0"
                or fmt.get("format_id") == "http_mp3_128"
                ):  # Prefer MP3 format
                return fmt.get("url", "")
        print('Cant found mp3 format')
        return None

    def _track_instance(self, data: dict) -> Track:
        return Track(
            track_id=data.get("id", ""),
            title=data.get("title", "Unknown"),
            artists=data.get("uploader", "Unknown"),
            duration=data.get("duration", 0),
            caption=( 
                f"<a href='{data.get('webpage_url', None)}'>" 
                f"{data.get('uploader', 'Unknown')} - {data.get('title', 'Unknown')}</a>" 
            ),
            link=data.get("webpage_url", None),
            download_link=self._get_download_link(data),
        )


# Example usage
async def main():
    sct = SoundCloudTool()
    # results = await sct.search_tracks("tokyophile")
    # print(f'Found {len(results)} tracks')
    # for i, track in enumerate(results):
    #     print(f'{i}: {track.download_link}')
    
    single_track = await sct.get_track('https://soundcloud.com/user-189585884/nasty-jumz-coolzone?si=fabbe70562de42d190c736bb94922d85&utm_source=clipboard&utm_medium=text&utm_campaign=social_sharing')
    await sct.save_track(single_track)

# asyncio.run(main())
