"""
    Simple tool to interact with unofficial YandexMusic API by MarshalX.
    https://github.com/MarshalX/yandex-music-api
    
    Can get, search, download tracks and prepare metadata 
    for easy use in your projects
    
    writed by: https://t.me/damirtag,
    -   for Damir's userbot
"""

import aiofiles, asyncio

from aiohttp import ClientSession

import typing, logging, re, os
from typing import Literal
from datetime import datetime
from dataclasses import dataclass, field

from yandex_music import (
    ClientAsync,
    Search,
    Track,
    TrackShort,
    TrackLyrics,
    Album,
    DownloadInfo,
    Chart,
    ChartInfo,
    Queue
)
from yandex_music.exceptions import NotFoundError, YandexMusicError


# SETTINGS BEGIN

# get your YandexMusic Token:
# https://yandex-music.readthedocs.io/en/main/token.html
# im using config file to store tokens
try:
    import config
    TOKEN = config.YANDEX_MUSIC_TOKEN
except (ImportError, NameError) as e:
    print(e)
    TOKEN: str = None # IF NO CONFIG FILE, JUST PASS YOUR TOKEN HERE

from pathlib import Path
path = Path()

TRACK_PATTERN = r"https://music\.yandex\.(?:ru|com|kz)/album/\d+/track/\d+"
ALBUM_PATTERN = r"https://music\.yandex\.(?:ru|com|kz)/album/\d+"
HOME_DIR = path.absolute()
CODEC = "mp3"
BITRATE = 320
CHART_OPTIONS = Literal[
    'world', 
    'kazakhstan', 
    'russia', 
    'armenia', 
    'georgia', 
    'azerbaijan', 
    'kyrgyzstan', 
    'moldova', 
    'tajikistan', 
    'turkmenistan', 
    'uzbekistan'
]
# SETTINGS END

@dataclass
class TrackData:
    id: int                           = None
    """Track ID"""
    album_id: int                     = None
    album_title: str                  = None 
    title: str                        = None
    duration: float                   = None
    """Duration converts to seconds"""
    artists: typing.List[str] = field(default_factory=list)
    caption: str                      = None
    """Artists and track title with hyperlink to track page in music.yandex.com, 
    uses HTML markdown"""
    bitrate: int                      = BITRATE
    """Standard 320 kbps (best)"""
    filename: str                     = None
    """Pattern: 'track_{id}.{codec}'"""
    download_info: list[DownloadInfo] = None
    cover: str                        = None
    genre: str                        = None
    year: int                         = None
    position: typing.Optional[int]    = None
    """Position in chart"""
    progress: typing.Optional[str]    = None
    """up, down, new, or same"""
    shift: typing.Optional[int]       = None
    lyrics_text: str                  = None

@dataclass
class ChartData:
    title: str
    description: str
    country: str
    tracks: typing.List['TrackData']
    update_time: datetime
    
    def __str__(self) -> str:
        return f"Chart: {self.title} ({self.country})\nTracks: {len(self.tracks)}"

@dataclass
class AlbumData:
    id: int                             = None
    title: str                          = None
    genre: str                          = None
    year: int                           = None
    release_date: str                   = None
    tracks: typing.List['TrackData']    = None
    track_count: int                    = None
    cover: str                          = None
    desc: str                           = None
    is_premiere: bool                   = None
    likes_count: int                    = None

class YandexMusicSDK:
    def __init__(
            self, 
            TOKEN: str = TOKEN,
            **kwargs
        ):
        self.client = ClientAsync(token=TOKEN, **kwargs)
        self.is_init = False
        self.logger = self._setup_logger()
        # print(TOKEN)
    
    async def __aenter__(self):
        await self.client.init()
        self.is_init = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.is_init = False

    def _setup_logger(self):
        logger = logging.getLogger()
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[yandex_music: %(funcName)s] %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not logger.handlers:
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    @staticmethod
    def _convert_to_seconds(milliseconds: int) -> float:
        return round(milliseconds / 1000, 2)
    
    @staticmethod
    def _extract_album_id(url: str) -> typing.Optional[int]:
        if not re.match(ALBUM_PATTERN, url):
            return None
        
        try:
            album_id = int(url.split('/')[-1])
            return album_id
        except (ValueError, IndexError):
            return None

    async def _request(
        self,
        url,
        params: dict = None,
        method: str = 'GET', 
        headers: dict = None
    ):
        """
        only direct api links
        """
        async with ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                headers=headers
            ) as response:
                data = await response.json()
                return data
        
    def _prepare_metadata(
        self,
        track: Track,
        album: Album,
        chart: typing.Optional[Chart] = None,
        lyrics_text: typing.Optional[str] = None,
        download_info: list[DownloadInfo] = None
    ) -> typing.Union[TrackData]:        
        return TrackData(
            id=track.id,
            album_id=album.id,
            album_title=album.title,
            title=track.title,
            duration=self._convert_to_seconds(track.duration_ms),
            artists=', '.join(a.name for a in track.artists),
            caption=( 
                f"<a href='https://music.yandex.com/album/{album.id}/track/{track.id}'>" 
                f"{', '.join(a.name for a in track.artists)} — {track.title}</a>" 
            ),
            filename=self._prepare_filename(track.id),
            download_info=download_info,
            cover=track.get_cover_url('1000x1000'),
            genre=(
                album.genre 
                if album.genre is not None else None
            ),
            year=(
                album.year 
                if album.year is not None else None
            ),
            position=chart.position if chart else None,
            progress=chart.progress if chart else None,
            shift=chart.shift       if chart else None,
            lyrics_text=lyrics_text
        )

    def insert_metadata(
        self,
        metadata: TrackData
    ):
        """
        Note:
            **Inserts metadata only for already downloaded track**

        Args:
            metadata: `TrackData` obj 
        """
        filename = self._prepare_filename(metadata.id)
        if filename and os.path.exists(filename):
            from mutagen.mp3 import MP3
            from mutagen.easyid3 import EasyID3
            import mutagen.id3
            try:
                self.logger.info(f"Starting metadata inserting: {metadata.title}")
                try:
                    audio = EasyID3(filename)
                except mutagen.id3.ID3NoHeaderError:
                    audio = MP3(filename)
                    audio.add_tags()
                    audio.tags.save(filename)
                    audio = EasyID3(filename)
                if metadata.album_title:
                    audio['album'] = metadata.album_title
                    if metadata.year:
                        audio['date'] = str(metadata.year)
                    if metadata.genre:
                        audio['genre'] = metadata.genre
                audio['title'] = metadata.title
                audio['artist'] = metadata.artists

                audio.save()
                self.logger.info(f"Updated metadata for: {metadata.title}")
            except Exception as e:
                self.logger.error(f"Error updating metadata: {str(e)}")
        else:
            self.logger.warning(
                'Sorry, the metadata inserting failed, ' 
                'seems like the track not downloaded'
            )

    def _prepare_album_metadata(
        self,
        album: Album,
        tracks: typing.List[TrackData] = None
    ) -> typing.Union[AlbumData]:
        """
        Prepare album metadata from Album object and optional list of track data.
        
        Args:
            album: Album object containing raw album information
            tracks: Optional list of prepared TrackData objects
            
        Returns:
            AlbumData object with formatted album metadata
        """
        return AlbumData(
            id=album.id,
            title=album.title,
            genre=album.genre if album.genre is not None else None,
            year=album.year if album.year is not None else None,
            release_date=album.release_date if hasattr(album, 'release_date') else None,
            tracks=tracks,
            track_count=len(tracks) if tracks is not None else album.track_count,
            cover=album.get_cover_url('1000x1000') if hasattr(album, 'get_cover_url') else None,
            desc=album.description if hasattr(album, 'description') else None,
            is_premiere=album.is_premiere if hasattr(album, 'is_premiere') else None,
            likes_count=album.likes_count if hasattr(album, 'likes_count') else None
        )

    @staticmethod    
    def _prepare_filename(id: int):
        return (
            f'track_{id}.{CODEC}'
            if id else None
        )

    async def _extract_track_id(self, track: typing.Union[str, int]) -> typing.Optional[str]:
        """Extract track ID from URL or input string/integer"""
        if isinstance(track, str):
            if re.match(TRACK_PATTERN, track):
                return track.split('/')[-1]
            elif track.isdigit():
                return track
        elif isinstance(track, int):
            return str(track)
        return None

    async def _get_lyrics(self, track: Track) -> typing.Optional[str]:
        "Helper function to get lyrics"""
        try:
            lyrics_data: TrackLyrics = await track.get_lyrics_async('TEXT')
            return await lyrics_data.fetch_lyrics_async()
        except NotFoundError:
            self.logger.error('Failed to get lyrics')
            return None

    async def _download(
            self, 
            dwnld_info: list[DownloadInfo],
            filename: typing.Optional[str],
            upload_dir: typing.Optional[str] = None
        ):
        self.logger.info(
            "Starting to download track\n"
            f"settings: codec = {CODEC}, bitrate = {BITRATE}kbps, filename = {filename}"
        )
        suitable_links = [
            info for info in dwnld_info if info['codec'] == CODEC 
            and info['bitrate_in_kbps'] == BITRATE
        ]
        
        if not suitable_links:
            self.logger.error("No direct links found")
            return
        download_url = suitable_links[0]['direct_link']

        download_path = filename
        if upload_dir:
            download_path = f'{upload_dir}/{filename}'
            Path(download_path).mkdir(exist_ok=True)
        
        if not os.path.exists(download_path):
            async with ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status == 200:
                        async with aiofiles.open(download_path, 'wb') as f:
                            await f.write(await response.read())
                        self.logger.info(f"Track saved to {download_path}")
                        return download_path
                    else:
                        self.logger.error("Error while downloading track")
                        return None
        self.logger.info('Track already exists, skipping download')
        return download_path 
        
    async def search(
        self,
        query: str,
        type: str = 'track',
        count: int = 10,
        download: bool = True,
        lyrics: bool = False,
        upload_dir: typing.Optional[str] = None
    ) -> list[TrackData]:
        """
        Optimized search function using parallel processing.
        """
        if not self.is_init:
            await self.client.init()
            self.is_init = True

        try:
            r: Search = await self.client.search(query, type_=type)
            if not r or not r.tracks or not r.tracks.results:
                raise NotFoundError("[yandex_music: search] Track not found")

            tracks = r.tracks.results[:count]
            
            async def process_track(track: Track):
                """Process a single track with all its metadata"""
                self.logger.info(
                    f'Found track: {track.title} | {self._convert_to_seconds(track.duration_ms)} sec'
                )
                
                album = track.albums[0] if track.albums else None
                
                # Parallel fetch of lyrics and download info
                lyrics_task = None
                if lyrics:
                    lyrics_task = asyncio.create_task(self._get_lyrics(track))
                
                download_task = asyncio.create_task(
                    track.get_download_info_async(True)
                )
                
                # Wait for both tasks to complete
                results = await asyncio.gather(
                    download_task,
                    lyrics_task if lyrics_task else asyncio.sleep(0),
                    return_exceptions=True
                )
                
                download_info, lyrics_text = results[0], results[1] if lyrics_task else None
                if isinstance(download_info, Exception):
                    self.logger.error(f'Failed to get download info: {download_info}')
                    return None
                
                # Prepare metadata
                metadata = self._prepare_metadata(
                    track,
                    album,
                    lyrics_text=None if isinstance(lyrics_text, Exception) else lyrics_text,
                    download_info=download_info
                )
                
                # Download if needed
                if download:
                    await self._download(
                        download_info,
                        self._prepare_filename(track.id),
                        upload_dir
                    )
                
                return metadata

            # Process all tracks in parallel
            tasks = [process_track(track) for track in tracks]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out None results and exceptions
            return [r for r in results if r is not None and not isinstance(r, Exception)]

        except Exception as e:
            self.logger.error(f"Error: {e}")
            return []

    async def get_track(
        self,
        track: typing.Union[str, int],  # Track URL/ID
        download: bool = False,
        lyrics: bool = False,
        upload_dir: typing.Optional[str] = None
    ) -> typing.Optional[TrackData]:
        """
        Get track data from either track URL or ID
        """
        if not self.is_init:
            await self.client.init()
            self.is_init = True

        try:
            # Extract track ID
            track_id = await self._extract_track_id(track)
            # print(track_id)
            if not track_id:
                raise ValueError("Incorrect Track ID or Track URL!")

            # Fetch track data
            track = await self.client.tracks(track_id)
            if not track or not track[0]:
                raise YandexMusicError("Failed to get track")

            track: Track = track[0]  # API returns list of tracks
            self.logger.info(f'Fetched track: {track.title} | {self._convert_to_seconds(track.duration_ms)} sec')
            
            # Get album info
            album = track.albums[0] if track.albums else None
            
            # Get lyrics if requested
            lyrics_text = None
            if lyrics:
                lyrics_text = await self._get_lyrics(track)
            
            # Get download info - без параллельной обработки
            download_info = await track.get_download_info_async(get_direct_links=True)
            
            # Download if requested
            if download:
                await self._download(
                    download_info,
                    self._prepare_filename(track_id),
                    upload_dir
                )

            # Prepare and return metadata
            return self._prepare_metadata(
                track,
                album,
                lyrics_text=lyrics_text,
                download_info=download_info
            )

        except Exception as e:
            self.logger.error(f"Error: {e}")
            return None
        
    async def get_currently_track(self, device: str, lyrics: bool = False):
        """
        Gets сurrent playing track
        
        Note:
            **Not works for my wave (моя волна)**

        To use this command you need to pass Yandex Music Auth token

        https://yandex-music.readthedocs.io/en/main/token.html
        
        Returns:
            `TrackData` Object of currently listening track, otherwise `None`
        """
        if not self.is_init:
            await self.client.init()
            self.is_init = True
        queues = await self.client.queues_list(device)
        if not queues:
            self.logger.error('Queue is empty, check device name')
            return None
        
        last_queue: Queue = await self.client.queue(queues[0].id)
        last_track_id = last_queue.get_current_track()
        last_track: Track = await last_track_id.fetch_track_async()
        album = last_track.albums[0] if last_track.albums else None
        lyrics_text = None

        if lyrics:
            try:
                lyrics_data: TrackLyrics = await last_track.get_lyrics_async('TEXT')
                lyrics_text = await lyrics_data.fetch_lyrics_async()
            except NotFoundError:
                self.logger.error('Failed to get lyrics')
        
        return TrackData(
            id=last_track.id,
            album_id=album.id,
            title=last_track.title,
            duration=self._convert_to_seconds(last_track.duration_ms),
            artists=', '.join(a.name for a in last_track.artists),
            caption=( 
                f"<a href='https://music.yandex.com/album/{album.id}/track/{last_track.id}'>" 
                f"{', '.join(a.name for a in last_track.artists)} — {last_track.title}</a>" 
            ),
            lyrics_text=lyrics_text
        )

    async def get_album(
        self,
        album: typing.Union[str, int], # Album URL/ID
    ) -> AlbumData:
        """
        Get album data from its link or id

        Args:
            Album (:obj:`str` | :obj:`int`): link | id

        Returns:
            AlbumData (:obj: `AlbumData`)
        """
        if not self.is_init:
            await self.client.init()
            self.is_init = True
        if isinstance(album, str):
            if re.match(ALBUM_PATTERN, album):
                album_id = self._extract_album_id(album)
                if album_id is None:
                    raise ValueError("Could not extract album ID from URL")
            else:
                try:
                    album_id = int(album)
                except ValueError:
                    raise ValueError("Invalid album ID format")
        else:
            album_id = album
        
        album_info = await self.client.albums_with_tracks(album_id)

        tracks_data = None
        if album_info.volumes:
            all_tracks = [track for volume in album_info.volumes for track in volume]
            tracks_data = [
                self._prepare_metadata(
                    track, 
                    album_info, 
                    download_info=await track.get_download_info_async(True)
                )
                for track in all_tracks
            ]

        return self._prepare_album_metadata(album_info, tracks_data)

    async def get_chart(
        self,
        chart_country: CHART_OPTIONS,
        download: bool = False,
        count: typing.Optional[int] = 10,
        upload_dir: typing.Optional[str] = None,
        *args,
        **kwargs
    ) -> ChartData:
        """
        Get chart data and optionally download tracks.
        
        Args:
            `chart_country`: Country code for the chart
            `download`: Whether to download the tracks
            `count`: Number of tracks to download (if download=True, default 10)
            `upload_dir`: Directory to save downloaded tracks
            
        Returns:
            `ChartData` object containing chart information
        """
        if not self.is_init:
            await self.client.init()
            self.is_init = True
        self.logger.info(f"[yandex_music: chart] Fetching chart for {chart_country.capitalize()}")
        
        # Get chart data from client
        chart: ChartInfo = await self.client.chart(chart_country, *args, **kwargs)
        tracks_short: typing.List[TrackShort] = chart.chart.tracks
        
        # Process tracks
        processed_tracks: typing.List[TrackData] = []
        
        self.logger.info(f"[yandex_music: chart] Processing full chart: {chart.title}")
        
        for idx, track_short in enumerate(tracks_short):
            track: Track = track_short.track
            chart_info: Chart = track_short.chart
            download_info = await track.get_download_info_async(True)
            
            track_data: TrackData = self._prepare_metadata(
                track=track,
                album=track.albums[0] if track.albums else None,
                chart=chart_info,
                download_info=download_info
            )
            
            processed_tracks.append(track_data)

            position_icon = {
                'down': '🔻',
                'up': '🔺',
                'new': '🆕'
            }.get(chart_info.progress, '▪️')
            
            if chart_info.position == 1:
                position_icon = '👑'
                
            self.logger.info(f"{position_icon} #{chart_info.position} {track_data.title} - {track_data.artists}")
            
            # Download if requested
            if download and (count is None or idx < count):
                self.logger.info(f"Queuing track {idx + 1}/{count if count else len(tracks_short)}")
                result = await self._download(
                    dwnld_info=download_info,
                    filename=self._prepare_filename(track.id),
                    upload_dir=upload_dir
                )
                if result:
                    self.logger.info(f"Successfully downloaded: {track_data.title}")
                else:
                    self.logger.error(f"Failed to download: {track_data.title}")
                # Add small delay between downloads
                await asyncio.sleep(0.5)
        
        # Create and return ChartData
        chart_data = ChartData(
            title=chart.title,
            description=chart.chart.description,
            country=chart_country,
            tracks=processed_tracks,
            update_time=datetime.now()
        )
        
        download_summary = f" and downloaded {count if count else len(processed_tracks)} tracks" if download else ""
        self.logger.info(f"\n Successfully processed {len(processed_tracks)} tracks{download_summary} from {chart_data.title}")
        return chart_data

async def main():    
    async with YandexMusicSDK() as ymsdk:
        import time
        # first_s = time.time()
        # result = await ymsdk.search('xxxmanera', download=False, lyrics=True)
        # first_end = time.time()
        # print(f"search() execution time: {first_end - first_s:.6f} sec")
        # print(result[0].download_info)
        first_s = time.time()
        track = await ymsdk.get_track(
            'https://music.yandex.kz/album/31926326/track/127718866', 
            download=False, 
            lyrics=False
        )
        first_end = time.time()
        print(f"get_track() execution time: {first_end - first_s:.6f} sec")
        print(track.download_info)

# try:
#     asyncio.run(main())
# except (KeyboardInterrupt, SystemExit):
#     print('sayonara')