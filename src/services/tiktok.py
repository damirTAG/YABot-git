"""
Author: https://github.com/damirTAG
GH repo: https://github.com/damirTAG/TikTok-Module
"""

import aiohttp, asyncio
import logging, os, re
import ffmpeg

from dataclasses import dataclass, field
from typing import Union, Optional, Literal, List, Dict
from tqdm.asyncio import tqdm


@dataclass
class data:
    dir_name: str
    media: Union[str, List[str]]
    type: Literal['images', 'video']

@dataclass
class metadata(data):
    metadata: Dict[str, Union[int, float]] = field(default_factory=dict)

    @property
    def height(self) -> Optional[int]:
        return self.metadata.get('height')
    @property
    def width(self) -> Optional[int]:
        return self.metadata.get('width')
    @property
    def duration(self) -> Optional[float]:
        return self.metadata.get('duration')

class TikTok:
    def __init__(self, host: Optional[str] = None):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPad; U; CPU OS 3_2 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) '
                          'Version/4.0.4 Mobile/7B334b Safari/531.21.10'
        }
        self.host = host or "https://www.tikwm.com/"
        self.session = None

        self.data_endpoint = "api"
        self.search_videos_keyword_endpoint = "api/feed/search"
        self.search_videos_hashtag_endpoint = "api/challenge/search"

        self.logger = self._setup_logger()
        self.result = None
        self.link = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _setup_logger(self):
        logger = logging.getLogger('damirtag.TikTok')
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[damirtag-TikTok:%(funcName)s]: %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not logger.handlers:
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    async def _ensure_data(self, link: str):
        if self.result is None or self.link != link:
            self.link = link
            self.result = await self.fetch(link)
            self.logger.info("Successfully ensured data from the link")

    async def _makerequest(self, endpoint: str, params: dict) -> dict:
        async with self.session.get(
                os.path.join(self.host, endpoint),
                params=params, 
                headers=self.headers
            ) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get('data', {})

    async def _download_file(self, url: str, path: str):
        async with self.session.get(url) as response:
            response.raise_for_status()
            with open(path, 'wb') as file, tqdm(unit='B', unit_scale=True, desc=os.path.basename(path)) as pbar:
                while chunk := await response.content.read(1024):
                    file.write(chunk)
                    pbar.update(len(chunk))

    @staticmethod
    def get_url(text: str) -> Optional[str]:
        urls = re.findall(r'http[s]?://[^\s]+', text)
        return urls[0] if urls else None

    async def image(self, download_dir: Optional[str] = None):
        download_dir = download_dir or self.result['id']
        os.makedirs(download_dir, exist_ok=True)
        tasks = [
            self._download_file(
                    url, 
                    os.path.join(
                        download_dir, 
                        f'image_{i + 1}.jpg'
                    )
                )
                for i, url in enumerate(self.result['images'])
            ]
        await asyncio.gather(*tasks)
        self.logger.info(f"Images - Downloaded and saved photos to {download_dir}")

        return data(
            dir_name=download_dir,
            media=[
                    os.path.join(
                        download_dir, 
                        f'image_{i + 1}.jpg'
                    ) 
                    for i in range(len(self.result['images']))
                ],
            type="images"
        )

    async def video(self, video_filename: Optional[str] = None, hd: bool = False):
        video_url = self.result['hdplay'] if hd else self.result['play']
        video_filename = video_filename or f"Greetings from @damirtag {self.result['id']}.mp4"

        async with self.session.get(video_url) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            with open(video_filename, 'wb') as file, tqdm(
                    total=total_size, 
                    unit='B', 
                    unit_scale=True, 
                    desc=video_filename
                ) as pbar:
                async for chunk in response.content.iter_any():
                    file.write(chunk)
                    pbar.update(len(chunk))

        self.logger.info(f"Video - Downloaded and saved video as {video_filename}")

        # Extract metadata (duration from API, width and height from ffmpeg)
        duration = self.result.get('duration', 0.0)  # Provided by the API
        width, height = self._get_video_dimensions(video_filename)

        return metadata(
            dir_name=os.path.dirname(video_filename),
            media=video_filename,
            type="video",
            metadata={
                'duration': duration,
                'width': width,
                'height': height
            }
        )

    def _get_video_dimensions(self, video_file: str):
        """Extract width and height using ffmpeg."""
        try:
            probe = ffmpeg.probe(video_file)
            video_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'video']
            if video_streams:
                width = video_streams[0]['width']
                height = video_streams[0]['height']
                return width, height
            else:
                self.logger.error(f"No video streams found in {video_file}")
                return None, None
        except Exception as e:
            self.logger.error(f"Error while extracting video dimensions with ffmpeg: {e}")
            return None, None
        
    async def fetch(self, link: str) -> dict:
        """
        Get tiktok post info (raw api response).

        :param: link(str) = Tiktok video url
        """
        url = self.get_url(link)
        params = {"url": url, "hd": 1}
        return await self._makerequest(self.data_endpoint, params=params)

    async def search(
            self, 
            method: Literal["keyword", "hashtag"], 
            keyword: str, 
            count: int = 10, 
            cursor: int = 0
            ) -> list:
        """
        Search videos by keyword (default search) or hashtag

        Args:
            method (Literal["keyword", "hashtag"]): The search method. Choose between 'keyword' for general video search or 'hashtag' for hashtag-based search.
            keyword (str): The keyword or hashtag to search for. For 'keyword', it can be a phrase or any string. For 'hashtag', prefix with `#` (e.g., '#funny').
            count (int, optional): The number of search results to return. Default is 10.
            cursor (int, optional): The cursor for pagination. Used to fetch subsequent pages of results. Default is 0.

        Returns:
            list: A list of search results returned by the TikTok API.
            Each entry in the list contains metadata for individual videos or hashtags.

            Example response to see: 
                https://tikwm.com/api/feed/search?keywords=jojo7&count=10&cursor=10

        Example:
            If you're searching for videos related to "jojo7" with 10 results:
                result = await search(method="keyword", keyword="jojo7", count=10, cursor=0)

            If you're searching for a specific hashtag like "#funny" with 5 results:
                result = await search(method="hashtag", keyword="funny", count=5, cursor=0)
        """
        self.logger.info(f"Searching for: {keyword}")
        params = {"keywords": keyword, "count": count, "cursor": cursor}
        endpoint = (
            self.search_videos_keyword_endpoint 
            if method == 'keyword' 
            else self.search_videos_hashtag_endpoint
        )

        try:
            data = await self._makerequest(endpoint, params=params)
            if data:
                total_results_int = (
                    f"{len(data.get('videos'))} videos" 
                    if method == "keyword" 
                    else f"{len(data.get('challenge_list'))} hashtags"
                )
                self.logger.info(f"Found {total_results_int} for query: {keyword}")
                return data.get("videos", []) if method == 'keyword' else data.get("challenge_list", [])
            else:
                raise Exception("Nothing found. Sorry, check params")
        except Exception as e:
            self.logger.error(f"Failed to search: {e}")    

    async def download_sound(
        self,
        link: Union[str],
        audio_filename: Optional[str] = None,
        audio_ext: str = ".mp3"
    ) -> str:
        await self._ensure_data(link)

        file_url = self.result.get('music_info', {}).get('play', '')
        if not file_url:
            file_url = self.result.get('play', '')
        if not file_url:
            raise ValueError("❌ No audio URL found in either 'music_info.play' or 'play'.")

        if not audio_filename:
            title = self.result.get('music_info', {}).get('title', 'audio')
            safe_title = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in title).strip()
            audio_filename = f"{safe_title}{audio_ext}"
        elif not audio_filename.endswith(audio_ext):
            audio_filename += audio_ext

        await self._download_file(file_url, audio_filename)
        self.logger.info(f"Sound - Downloaded and saved sound as {audio_filename}")
        return audio_filename

    async def download(
            self, 
            link: Union[str], 
            video_filename: Optional[str] = None, 
            hd: bool = False
            ) -> str:
        """
        Asynchronously downloads a TikTok video or photo post.

        Args:
            video_filename (Optional[str]): The name of the file for the TikTok video or photo. If None, the file will be named based on the video or photo ID.
            hd (bool): If True, downloads the video in HD format. Defaults to False.
            metadata (bool): if True, returns duration, width and height (only for videos)

        Returns:
            dir_name (Union[str]): Directory name.
            media (List[str]): Full list of downloaded media.
            type (str): The type of downloaded objects: Images or video.
            metadata (dict): {'duration': 13, 'width': 576, 'height': 1024}

        Raises:
            Exception: No downloadable content found in the provided link.

        Base usage code example:
            ```python
            import asyncio
            from tiktok import TikTok

            async def main():
                async with TikTok() as tt:
                    video = await tt.download("https://www.tiktok.com/@adasf4v/video/7367017049136172320", hd=True)
                    # or
                    photo = await tt.download('https://www.tiktok.com/@arcadiabayalpha/photo/7375880582473043232', 'tiktok_images')
                    print(f"Downloaded video: {video.media}")
                    print(f"Images downloaded to: {photo.dir_name}")

            asyncio.run(main())
            ```
        """
        await self._ensure_data(link)
        if 'images' in self.result:
            self.logger.info("Starting to download images")
            return await self.image(video_filename)
        elif 'hdplay' in self.result or 'play' in self.result:
            self.logger.info("Starting to download video.")
            return await self.video(video_filename, hd)
        else:
            self.logger.error("No downloadable content found in the provided link.")
            raise Exception("No downloadable content found in the provided link.")