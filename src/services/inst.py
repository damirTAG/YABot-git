from urllib.parse import urlparse, unquote
import yt_dlp

import logging
import aiohttp
import asyncio
import os


logger = logging.getLogger()
semaphore = asyncio.Semaphore(20)


async def download_inst_post(session: aiohttp.ClientSession, url, download_dir):
    """
    Downloads Instagram posts (images/videos) directly via URL.
    """
    async with semaphore:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
            if response.status == 404:
                logger.info(f"[Instagram:post] | No file found at {url} (404)")
                return False
            
            if response.status != 200:
                logger.warning(f"[Instagram:post] | Error fetching {url}. Status: {response.status}")
                return False

            # Detect file type from Content-Type header
            content_type = response.headers.get('Content-Type', '')
            if "image" in content_type:
                ext = ".jpg"
            elif "video" in content_type:
                ext = ".mp4"
            else:
                logger.warning(f"[Instagram:post] | Unsupported content type: {content_type} at {url}")
                return False

            content = await response.read()
            if len(content) < 500:  # Avoid empty pages (0-byte or small HTML error pages)
                logger.warning(f"[Instagram:post] | Empty file detected at {url}. Skipping.")
                return False

            parsed_url = urlparse(url)
            filename = unquote(os.path.basename(parsed_url.path)) + ext
            file_path = os.path.join(download_dir, filename)

            with open(file_path, 'wb') as f:
                f.write(content)

            logger.info(f"[Instagram:post] | Downloaded: {filename}")
            return True


async def download_instagram_reel(url: str, download_dir: str, filename: str = None):
    """
    Downloads Instagram reels using yt-dlp.
    
    :param url: Instagram reel URL
    :param download_dir: Directory to save the downloaded file
    :param filename: Optional custom filename (without extension)
    """
    os.makedirs(download_dir, exist_ok=True)
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(download_dir, f'{filename or "%(id)s"}.%(ext)s'),
        'quiet': False,
        'no_warnings': False,
        'extract_flat': False,
        'cookiefile': None,  # Add cookie file path if needed for authenticated content
    }
    
    try:
        # Run yt-dlp in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _download_with_ytdlp, url, ydl_opts)
        logger.info(f"[Instagram:reel] | Successfully downloaded: {url}")
        return True
    except Exception as e:
        logger.exception(f"[Instagram:reel] | Error downloading {url}: {e}")
        return False


def _download_with_ytdlp(url: str, ydl_opts: dict):
    """
    Helper function to download with yt-dlp (runs in executor).
    """
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


async def download_instagram_content(url: str, download_dir: str, filename: str = None):
    """
    Smart downloader that detects content type and uses appropriate method.
    
    :param url: Instagram URL (post or reel)
    :param download_dir: Directory to save the downloaded file
    :param filename: Optional custom filename
    """
    # Check if it's a reel
    if '/reel/' in url or '/reels/' in url:
        return await download_instagram_reel(url, download_dir, filename)
    else:
        # For regular posts, use direct download
        async with aiohttp.ClientSession() as session:
            return await download_inst_post(session, url, download_dir)


# Example usage
async def main():
    # Download a reel
    reel_url = "https://www.instagram.com/reel/DGYQXZOAciJ/"
    await download_instagram_reel(reel_url, "./downloads", "my_reel")
    
    # Or use smart downloader
    # await download_instagram_content(reel_url, "./downloads", "my_video")


# if __name__ == "__main__":
#     asyncio.run(main())