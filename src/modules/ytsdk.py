import os, sys, datetime
import logging
import asyncio
import yt_dlp

from dataclasses import dataclass
from typing import List, Dict, Optional, Any



@dataclass
class VideoMetadata:
    """Dataclass for video metadata."""
    id: str
    url: str
    title: str
    channel: str
    duration: int
    view_count: Optional[int] = None
    description: Optional[str] = None
    upload_date: Optional[str] = None
    thumbnail: Optional[str] = None
    download_url: Optional[str] = None
    filesize: Optional[int] = None


class YouTubeSDK:
    """Optimized SDK for downloading and interacting with YouTube videos, designed for Telegram bot integration."""
    
    def __init__(self, output_dir: str = "downloads", 
                 quality: str = "480p", 
                 log_level: int = logging.INFO,
                 max_filesize: Optional[int] = None,
                 cookies_file: Optional[str] = None):
        """
        Initialize the YouTubeSDK.
        
        Args:
            output_dir: Directory to save downloaded files
            quality: Video quality to download ('720p', '480p', '360p')
            log_level: Logging level
            max_filesize: Maximum file size in bytes (for Telegram limits)
            cookies_file: Path to cookies file for accessing private videos
        """
        self.output_dir = os.path.abspath(output_dir)
        self.quality = quality
        self.cookies_file = cookies_file
        self.max_filesize = max_filesize
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Set up logging
        self.logger = logging.getLogger("YouTubeSDK")
        self.logger.setLevel(log_level)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
        self.logger.info(f"YouTubeSDK initialized. Output directory: {self.output_dir}")
    
    def _get_base_options(self) -> Dict[str, Any]:
        """Get optimized base options for yt-dlp."""
        options = {
            'format': self._get_format_string(),
            'outtmpl': os.path.join(self.output_dir, 'Greetings from @damirtag yt id %(id)s.%(ext)s'),
            'noplaylist': True,
            'progress_hooks': [self._progress_hook],
            'quiet': True,  # Less verbose output for better performance
            'verbose': False,
            'no_warnings': True,  # Suppress warnings
            'socket_timeout': 10,  # Shorter timeout for better performance
            'retries': 3,  # Retry on failure
            'ignoreerrors': True,  # Skip unavailable videos
            'no_color': True,  # Disable colors in output for cleaner logs
            'noprogress': False,  # Show progress for monitoring
            'merge_output_format': 'mp4',  # Ensure MP4 output format
        }
        
        if self.max_filesize:
            options['max_filesize'] = self.max_filesize
            
        if self.cookies_file and os.path.exists(self.cookies_file):
            options['cookiefile'] = self.cookies_file
            
        return options
    
    def _get_format_string(self) -> str:
        """Get optimized format string for mid-quality videos."""
        quality_map = {
            '720p': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
            '480p': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480][ext=mp4]+bestaudio/best[height<=480][ext=mp4]/best[height<=480]/best[ext=mp4]/best',
            '360p': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360][ext=mp4]+bestaudio/best[height<=360][ext=mp4]/best[height<=360]/best[ext=mp4]/best',
            'audio': 'bestaudio[ext=m4a]/bestaudio',
            'mp3': 'bestaudio[ext=m4a]/bestaudio',
        }
        
        # Default to 480p if quality not specified
        return quality_map.get(self.quality, quality_map['480p'])
    
    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """Simplified progress hook for performance."""
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', 'N/A')
            self.logger.debug(f"Downloading: {percent} complete")
        elif d['status'] == 'finished':
            self.logger.info(f"Download complete: {d['filename']}")
    
    async def _run_yt_dlp(self, url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run yt-dlp in a separate thread with optimizations."""
        loop = asyncio.get_event_loop()
        
        def _extract_info():
            with yt_dlp.YoutubeDL(options) as ydl:
                return ydl.extract_info(url, download=options.get('skip_download', False) is False)
        
        return await loop.run_in_executor(None, _extract_info)
    
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        Get essential information about a YouTube video.
        
        Args:
            url: YouTube URL
            
        Returns:
            Dictionary containing video information
        """
        self.logger.info(f"Fetching info for: {url}")
        
        ydl_opts = self._get_base_options()
        ydl_opts.update({
            'skip_download': True,
            'writeinfojson': False,
            'writedescription': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
        })
        
        try:
            info = await self._run_yt_dlp(url, ydl_opts)
            return info
        except Exception as e:
            self.logger.error(f"Error fetching video info: {str(e)}")
            raise
    
    async def download(self, url: str, audio_only: bool = False, duration_limit: int = 360) -> str:
        """
        Download a YouTube video/audio optimized for Telegram.
        
        Args:
            url: YouTube video URL
            audio_only: If True, download audio only
            duration_limit: set dur limit to videos/audio if exceeds then downloads aborts, default 6 min (360 seconds)
            
        Returns:
            Path to downloaded file
        """
        self.logger.info(f"Downloading video: {url}")
        
        # Set temporary quality if audio_only is True
        original_quality = self.quality
        if audio_only:
            self.quality = 'mp3'
            
        ydl_opts = self._get_base_options()
        
        # Add post-processing for audio-only downloads
        if audio_only:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',  # Lower quality for faster downloads
                }],
            })
            
        try:
            info: dict = await self._run_yt_dlp(url, ydl_opts)

            duration = info.get('duration', None)
            if duration and duration >= duration_limit:
                return Exception(
                    'Video is longer than {} seconds. Download aborted.'.format(duration_limit)
                )
                
            # Get the downloaded file path
            if 'entries' in info:  # It's a playlist
                logging.info('[youtube] its a playlist')
                downloaded_file = os.path.join(
                    self.output_dir, 
                    f"{info['entries'][0]['title']}.mp4" if not audio_only else f"{info['entries'][0]['title']}.mp3"
                )
            else:  # It's a single video
                if audio_only:
                    downloaded_file = os.path.join(
                        self.output_dir, 
                        f"Greetings from @damirtag yt id {info['id']}.mp3"
                    )
                else:
                    downloaded_file = os.path.join(
                        self.output_dir, 
                        f"Greetings from @damirtag yt id {info['id']}.mp4"
                    )
            
            # Restore original quality setting
            self.quality = original_quality
            
            # Verify file exists
            if os.path.exists(downloaded_file):
                return downloaded_file
            
            # If file doesn't exist with .mp4 extension, look for other extensions
            if not audio_only and not os.path.exists(downloaded_file):
                base_path = os.path.join(self.output_dir, f"Greetings from @damirtag yt id {info['id']}.mp4")
                for ext in ['.mp4', '.mkv', '.webm']:
                    if os.path.exists(base_path + ext):
                        return base_path + ext
            
            return downloaded_file
        except Exception as e:
            # Restore original quality setting in case of error
            self.quality = original_quality
            self.logger.error(f"Error downloading video: {str(e)}")
            raise

    
    async def search_youtube(self, query: str, max_results: int = 5) -> List[VideoMetadata]:
        """
        Search YouTube for videos with optimized metadata retrieval.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of VideoMetadata objects
        """
        self.logger.info(f"Searching YouTube for: {query}")
        
        # Construct a YouTube search URL
        search_url = f"ytsearch{max_results}:{query}"
        
        ydl_opts = self._get_base_options()
        ydl_opts.update({
            'skip_download': True,
            'extract_flat': False,
            'youtube_include_dash_manifest': False,
        })
        
        try:
            info = await self._run_yt_dlp(search_url, ydl_opts)
            
            results = []
            if 'entries' in info:
                for entry in info['entries']:
                    download_url = None
                    print(entry)
                    if 'formats' in entry and len(entry['formats']) > 0:
                        # Find the appropriate format
                        for format_info in entry['formats']:
                            if format_info.get('ext') == 'mp4' and format_info.get('height', 0) <= 480:
                                download_url = format_info['url']
                        
                        # If no suitable format found, return the first one
                        if info['formats']:
                            download_url = info['formats'][0]['url']
                    video_id = entry.get('id', '')
                    
                    # Create VideoMetadata instance with essential info
                    metadata = VideoMetadata(
                        id=video_id,
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        title=entry.get('title', ''),
                        channel=entry.get('channel', ''),
                        duration=entry.get('duration', 0),
                        view_count=entry.get('view_count'),
                        thumbnail=entry.get('thumbnail'),
                        download_url=download_url
                    )
                    results.append(metadata)
            
            return results
        except Exception as e:
            self.logger.error(f"Error searching YouTube: {str(e)}")
            raise
    
    async def get_download_url(self, video_id: str) -> str:
        """
        Get direct download URL for a video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Direct download URL
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        ydl_opts = self._get_base_options()
        ydl_opts.update({
            'skip_download': True,
            'format': self._get_format_string(),
            'youtube_include_dash_manifest': False,  # Faster
        })
        
        try:
            info = await self._run_yt_dlp(url, ydl_opts)
            
            # Extract download URL
            if 'url' in info:
                return info['url']
            elif 'formats' in info and len(info['formats']) > 0:
                # Find the appropriate format
                for format_info in info['formats']:
                    if format_info.get('ext') == 'mp4' and format_info.get('height', 0) <= 480:
                        return format_info['url']
                
                # If no suitable format found, return the first one
                if info['formats']:
                    return info['formats'][0]['url']
            
            return ""
        except Exception as e:
            self.logger.error(f"Error getting download URL: {str(e)}")
            raise
            
    async def batch_download(self, urls: List[str], audio_only: bool = False) -> List[str]:
        """
        Download multiple YouTube videos asynchronously with optimized concurrency.
        
        Args:
            urls: List of YouTube video URLs
            audio_only: If True, download audio only
            
        Returns:
            List of paths to downloaded files
        """
        self.logger.info(f"Batch downloading {len(urls)} videos")
        
        # Process in batches to avoid overwhelming the system
        batch_size = 3  # Process 3 videos at a time
        results = []
        
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i+batch_size]
            tasks = [self.download_video(url, audio_only=audio_only) for url in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(batch_results)
            
            # Small delay between batches to prevent rate limiting
            if i + batch_size < len(urls):
                await asyncio.sleep(1)
        
        return [r for r in results if not isinstance(r, Exception)]
    
    async def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up old downloaded files to free up space.
        
        Args:
            max_age_hours: Maximum age of files in hours
            
        Returns:
            Number of files deleted
        """
        self.logger.info(f"Cleaning up files older than {max_age_hours} hours")
        
        count = 0
        now = datetime.datetime.now()
        
        for file in os.listdir(self.output_dir):
            file_path = os.path.join(self.output_dir, file)
            if os.path.isfile(file_path):
                # Get file modification time
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                age = now - mtime
                
                # Delete if older than max_age_hours
                if age.total_seconds() > max_age_hours * 3600:
                    try:
                        os.remove(file_path)
                        count += 1
                    except Exception as e:
                        self.logger.error(f"Error deleting file {file_path}: {str(e)}")
        
        self.logger.info(f"Deleted {count} old files")
        return count


# Example of how to use the SDK with a Telegram bot
async def example_telegram_usage():
    """Example showing how to use YouTubeSDK with a Telegram bot."""
    
    # Initialize SDK with Telegram-friendly settings
    youtube = YouTubeSDK(
        output_dir="telegram_downloads",
        quality="720p",  # Medium quality for faster downloads
        max_filesize=50 * 1024 * 1024,  # 50MB limit for Telegram
        cookies_file='yt_cookies.txt'
    )
    
    short = await youtube.search_youtube(
        'airbus ptu sound'
    )
    # print(short)


# This section would be activated in a real implementation
if __name__ == "__main__":
    asyncio.run(example_telegram_usage())