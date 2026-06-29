"""
Download dispatchers.

- ``download_single_video`` resolves a raw link to a single local file (used by
  the message-side flows that upload files to Telegram).
- ``resolve_inline_media`` resolves a link to direct CDN URLs (no download) for
  inline results, which Telegram fetches itself.
"""

import logging
import os

from config.enums import Patterns
from services.inst import download_instagram_reel, resolve_instagram_media
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
        return result.media if result else None  # type: ignore


async def _download_reel(link: str, download_dir: str) -> str | None:
    reel_url = await tools.convert_share_urls(link) or link
    shortcode = reel_url.rstrip("/").split("/")[-1].split("?")[0]

    if not await download_instagram_reel(reel_url, download_dir, shortcode):
        return None

    path = os.path.join(download_dir, f"{shortcode}.mp4")
    return path if os.path.exists(path) else None


async def resolve_inline_media(link: str) -> list[dict]:
    """Resolve a link to direct media descriptors for inline results.

    Returns ``[{"type": "video"|"photo", "url": ..., "thumb": ...}]`` with public
    CDN URLs that Telegram can fetch directly — no local download. Empty list for
    unsupported links.
    """
    if Patterns.TIKTOK.value.match(link):
        return await _resolve_tiktok_inline(link)

    if Patterns.INST_REELS.value.match(link):
        return await _resolve_instagram_inline(link)

    logger.info(f"[downloader] | Unsupported inline link: {link}")
    return []


async def _resolve_tiktok_inline(link: str) -> list[dict]:
    async with TikTok() as tt:
        await tt._ensure_data(link)
        result = tt.result or {}

        # Photo carousel -> one inline photo result per image.
        if "images" in result:
            cover = result.get("cover")
            return [
                {"type": "photo", "url": img, "thumb": cover or img} for img in result["images"]
            ]

        play = result.get("hdplay") or result.get("play")
        if not play:
            return []
        thumb = result.get("cover") or result.get("origin_cover") or play
        return [{"type": "video", "url": play, "thumb": thumb}]


async def _resolve_instagram_inline(link: str) -> list[dict]:
    reel_url = await tools.convert_share_urls(link) or link
    return await resolve_instagram_media(reel_url)
