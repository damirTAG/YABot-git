"""
Single-object video dispatcher.

Resolves a raw link (TikTok video or Instagram reel/share) to a single local
video file. Used by the inline download flow, which can only deliver one media
object — so anything multi-object (TikTok photo carousels, Instagram /p/ posts)
is intentionally rejected here.
"""

import logging
import os

from config.enums import Patterns
from services.inst import download_instagram_reel
from services.tiktok import TikTok
from utils import Tools

logger = logging.getLogger()
tools = Tools()


async def download_single_video(link: str, download_dir: str) -> str | None:
    """Download a single-object video to disk.

    Returns the local file path, or ``None`` if the link isn't a supported
    single video (e.g. a TikTok photo carousel) or the download failed.
    """
    os.makedirs(download_dir, exist_ok=True)

    if Patterns.TIKTOK.value.match(link):
        return await _download_tiktok_video(link, download_dir)

    if Patterns.INST_REELS.value.match(link):
        return await _download_reel(link, download_dir)

    logger.info(f"[downloader] | Unsupported single-video link: {link}")
    return None


async def _download_tiktok_video(link: str, download_dir: str) -> str | None:
    async with TikTok() as tt:
        await tt._ensure_data(link)
        if not tt.result:
            return None
        # Photo carousels carry an "images" key — not a single video.
        if "images" in tt.result:
            logger.info("[downloader] | TikTok photo post — not a single video, skipping")
            return None

        vid_id = tt.result.get("id", "tiktok")
        out_path = os.path.join(download_dir, f"{vid_id}.mp4")
        result = await tt.download(link, video_filename=out_path)
        return result.media if result else None # type: ignore


async def _download_reel(link: str, download_dir: str) -> str | None:
    reel_url = await tools.convert_share_urls(link) or link
    shortcode = reel_url.rstrip("/").split("/")[-1].split("?")[0]

    if not await download_instagram_reel(reel_url, download_dir, shortcode):
        return None

    path = os.path.join(download_dir, f"{shortcode}.mp4")
    return path if os.path.exists(path) else None
