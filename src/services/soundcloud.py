import asyncio
import os
from dataclasses import dataclass

import aiohttp
import requests
import yt_dlp
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC

PATTERN = r"(https://soundcloud\.com/[^/]+)"


@dataclass
class Track:
    track_id: str = None
    title: str = None
    artists: str = None
    duration: int = None  # Duration in seconds
    caption: str = None
    link: str = None
    download_link: str = None
    cover: str = None 


class SoundCloudTool:
    YTDL_OPTS = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "default_search": "scsearch",
        "quiet": True,
        "extract_flat": "in_playlist",  # Get basic info without full extraction
        "ignoreerrors": True,  # Skip broken tracks
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    def __init__(self):
        self.ytdl = yt_dlp.YoutubeDL(self.YTDL_OPTS)

    async def search_tracks_fast(self, query: str, count: int = 10) -> list[Track]:
        """
        Fast search that returns basic info without fetching full track details.
        Note: download_link will not be available with this method.
        """
        search_query = f"scsearch{count}:{query}"
        loop = asyncio.get_running_loop()

        try:
            data = await loop.run_in_executor(None, self.ytdl.extract_info, search_query, False)
        except Exception as e:
            print(f"Search error: {e}")
            return []

        tracks = []
        if "entries" in data:
            for entry in data["entries"]:
                if not entry:
                    continue

                # Use webpage_url instead of url (which contains API URL)
                webpage_url = entry.get("webpage_url", "")
                if not webpage_url or "soundcloud.com" not in webpage_url:
                    print(
                        f"Skipping entry without valid webpage_url: {entry.get('title', 'Unknown')}"
                    )
                    continue

                track = Track(
                    track_id=entry.get("id", ""),
                    title=entry.get("title", "Unknown"),
                    artists=entry.get("uploader", "Unknown"),
                    duration=entry.get("duration", 0),
                    caption=f"<a href='{webpage_url}'>{entry.get('uploader', 'Unknown')} - {entry.get('title', 'Unknown')}</a>",
                    link=webpage_url,
                    download_link=None,  # Not available in flat mode
                )
                tracks.append(track)

        return tracks

    async def search_tracks(self, query: str, count: int = 10) -> list[Track]:
        """
        Search for tracks on SoundCloud.
        Returns a list of Track objects with valid webpage URLs.
        """
        search_query = f"scsearch{count}:{query}"
        loop = asyncio.get_running_loop()

        try:
            # First get flat playlist with basic info
            data = await loop.run_in_executor(None, self.ytdl.extract_info, search_query, False)
        except Exception as e:
            print(f"Search error: {e}")
            return []

        tracks = []
        if "entries" in data:
            for entry in data["entries"]:
                if not entry:
                    continue

                # Use webpage_url which contains the proper SoundCloud URL
                webpage_url = entry.get("webpage_url", "")

                # Skip invalid URLs
                if not webpage_url or "soundcloud.com" not in webpage_url:
                    print(f"Skipping entry without valid URL: {entry.get('title', 'Unknown')}")
                    continue

                try:
                    # Fetch full track info using the webpage URL
                    track = await self.get_track(webpage_url)
                    if track and track.link:
                        tracks.append(track)
                except Exception as e:
                    print(f"Error fetching track info for {webpage_url}: {e}")
                    continue

        return tracks

    async def get_track(self, track_url: str) -> Track:
        """
        Get a single track by URL.
        """
        loop = asyncio.get_running_loop()
        try:
            data = await loop.run_in_executor(None, self.ytdl.extract_info, track_url, False)
            return self._track_instance(data)
        except Exception as e:
            print(f"Error fetching track: {e}")
            return None

    async def download_track(self, track_url: str, output_folder: str = "audio") -> str:
        """
        Download a track directly using yt-dlp (recommended method).
        Returns the path to the downloaded file.
        """
        os.makedirs(output_folder, exist_ok=True)

        # Get track info first
        track = await self.get_track(track_url)
        if not track:
            raise Exception("Could not fetch track info")

        output_template = os.path.join(output_folder, f"track_{track.track_id}.%(ext)s")

        ydl_opts = {
            **self.YTDL_OPTS,
            "outtmpl": output_template,
        }

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([track_url]))

        # Find the downloaded file
        output_file = os.path.join(output_folder, f"track_{track.track_id}.mp3")

        if os.path.exists(output_file):
            self._insert_metadata(output_file, track.title, track.artists)
            return output_file
        else:
            raise Exception("Download completed but file not found")

    async def save_track(self, track: Track, output_folder: str = "audio") -> str:
        """
        Save a track from its download link (legacy method).
        Use download_track() for better reliability.
        """
        if not track.download_link:
            raise Exception("No download link available for this track")

        os.makedirs(output_folder, exist_ok=True)
        output_file = os.path.join(output_folder, f"track_{track.track_id}.mp3")

        async with aiohttp.ClientSession() as session:
            async with session.get(track.download_link) as response:
                if response.status == 200:
                    with open(output_file, "wb") as f:
                        f.write(await response.read())
                else:
                    raise Exception(f"Download failed with status {response.status}")

        self._insert_metadata(
            output_file, track.title, track.artists, track.cover
        )
        return output_file

    @staticmethod
    def _insert_metadata(
        file_path: str,
        title: str,
        artist: str,
        cover: str | None = None
    ):
        try:
            audio = MP3(file_path, ID3=EasyID3)

            audio["title"] = title
            audio["artist"] = artist
            audio.save()

            if cover:
                response = requests.get(cover, timeout=10)
                response.raise_for_status()

                tags = ID3(file_path)
                tags.delall("APIC")

                tags.add(
                    APIC(
                        encoding=3,
                        mime=response.headers.get(
                            "Content-Type",
                            "image/jpeg"
                        ),
                        type=3,
                        desc="Cover",
                        data=response.content,
                    )
                )

                tags.save()

        except Exception as e:
            print(f"Warning: Could not insert metadata: {e}")

    @staticmethod
    def _get_download_link(entry: dict) -> str | None:
        """Extract direct download link from formats."""
        formats: list = entry.get("formats", [])

        # Try to find MP3 format
        for fmt in formats:
            if fmt.get("ext") == "mp3" and (
                fmt.get("format_id") == "http_mp3_128" or fmt.get("format_id") == "http_mp3_1_0"
            ):
                return fmt.get("url", "")

        # Fallback to any audio format
        for fmt in formats:
            if fmt.get("acodec") != "none" and fmt.get("url"):
                return fmt.get("url")

        return None

    def _track_instance(self, data: dict) -> Track | None:
        """Create Track instance from yt-dlp data."""
        if not data:
            return None

        # Get webpage URL, skip API URLs
        webpage_url = data.get("webpage_url", data.get("url", ""))

        # Skip if it's an API URL
        if "api.soundcloud.com" in webpage_url:
            print(f"Skipping API URL: {webpage_url}")
            return None

        return Track(
            track_id=data.get("id", ""),
            title=data.get("title", "Unknown"),
            artists=data.get("uploader", "Unknown"),
            duration=data.get("duration", 0),
            caption=(
                f"<a href='{webpage_url}'>"
                f"{data.get('uploader', 'Unknown')} - {data.get('title', 'Unknown')}</a>"
            ),
            link=webpage_url,
            download_link=self._get_download_link(data),  # type: ignore
            cover=data.get("thumbnail", None) # type: ignore
        )


# Example usage
async def main():
    sct = SoundCloudTool()

    # Test search
    print("Searching for tracks...")
    results = await sct.search_tracks("tokyophile", count=5)
    print(f"Found {len(results)} valid tracks\n")

    for i, track in enumerate(results, 1):
        print(f"{i}. {track.artists} - {track.title}")
        print(f"   URL: {track.link}")
        print(f"   Download link: {track.download_link}\n")

    # Test single track
    # print("\nFetching single track...")
    # single_track = await sct.get_track(
    #     'https://soundcloud.com/user-189585884/nasty-jumz-coolzone?si=fabbe70562de42d190c736bb94922d85&utm_source=clipboard&utm_medium=text&utm_campaign=social_sharing'
    # )

    # if single_track:
    #     print(f'Track: {single_track.artists} - {single_track.title}')

    #     # Download using yt-dlp (recommended)
    #     print("\nDownloading track...")
    #     output_file = await sct.download_track(single_track.link)
    #     print(f'Downloaded to: {output_file}')


# if __name__ == "__main__":
#     asyncio.run(main())
