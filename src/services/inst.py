import asyncio
import logging
import os
from urllib.parse import unquote, urlparse

import aiohttp

from config.settings import COBALT_API_KEY, COBALT_API_URL

logger = logging.getLogger()
semaphore = asyncio.Semaphore(20)

# Headers for talking to the self-hosted cobalt instance.
_COBALT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}
if COBALT_API_KEY:
    _COBALT_HEADERS["Authorization"] = f"Api-Key {COBALT_API_KEY}"

# Total time budget for resolving + streaming a single reel.
_COBALT_TIMEOUT = aiohttp.ClientTimeout(total=180)


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
                logger.warning(
                    f"[Instagram:post] | Error fetching {url}. Status: {response.status}"
                )
                return False

            # Detect file type from Content-Type header
            content_type = response.headers.get("Content-Type", "")
            if "image" in content_type:
                ext = ".jpg"
            elif "video" in content_type:
                ext = ".mp4"
            else:
                logger.warning(
                    f"[Instagram:post] | Unsupported content type: {content_type} at {url}"
                )
                return False

            content = await response.read()
            if len(content) < 500:  # Avoid empty pages (0-byte or small HTML error pages)
                logger.warning(f"[Instagram:post] | Empty file detected at {url}. Skipping.")
                return False

            parsed_url = urlparse(url)
            filename = unquote(os.path.basename(parsed_url.path)) + ext
            file_path = os.path.join(download_dir, filename)

            with open(file_path, "wb") as f:
                f.write(content)

            logger.info(f"[Instagram:post] | Downloaded: {filename}")
            return True


async def _cobalt_request(session: aiohttp.ClientSession, url: str) -> dict:
    """Low-level POST to the cobalt instance. Returns the raw JSON response."""
    payload = {
        "url": url,
        "videoQuality": "720",
        "downloadMode": "auto",
        "filenameStyle": "basic",
    }

    async with session.post(COBALT_API_URL, headers=_COBALT_HEADERS, json=payload) as resp:
        # cobalt always answers with JSON, even on errors.
        data = await resp.json(content_type=None)

    logger.info(f"[cobalt] | {url} -> status={data.get('status')}")
    return data


async def _resolve_cobalt_media(session: aiohttp.ClientSession, url: str) -> str | None:
    """Resolve a single direct media URL (used for reels).

    Returns the direct (tunnel/redirect) URL on success, or ``None`` if cobalt
    couldn't process the link. For picker responses the first video is chosen.
    """
    data = await _cobalt_request(session, url)
    status = data.get("status")

    if status in ("tunnel", "redirect"):
        return data.get("url")

    if status == "picker":
        items = data.get("picker") or []
        chosen = next((i for i in items if i.get("type") == "video"), None)
        chosen = chosen or (items[0] if items else None)
        return chosen.get("url") if chosen else None

    if status == "error":
        logger.warning(f"[cobalt] | Error resolving {url}: {data.get('error')}")
        return None

    logger.warning(f"[cobalt] | Unexpected response for {url}: {data}")
    return None


async def _resolve_cobalt_post(session: aiohttp.ClientSession, url: str) -> list[dict]:
    """Resolve every item of a post/carousel.

    Returns an ordered list of items shaped like ``{"type": ..., "url": ...}``.
    Single-media posts come back as a one-element list. Empty list on failure.
    """
    data = await _cobalt_request(session, url)
    status = data.get("status")

    if status in ("tunnel", "redirect"):
        return [{"type": None, "url": data.get("url"), "filename": data.get("filename")}]

    if status == "picker":
        return [i for i in (data.get("picker") or []) if i.get("url")]

    if status == "error":
        logger.warning(f"[cobalt] | Error resolving {url}: {data.get('error')}")
    else:
        logger.warning(f"[cobalt] | Unexpected response for {url}: {data}")
    return []


async def _stream_to_file(session: aiohttp.ClientSession, media_url: str, out_path: str) -> bool:
    """Stream a media URL to disk in chunks. Returns False on a bad/empty file."""
    async with session.get(media_url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
        if resp.status != 200:
            logger.warning(f"[cobalt] | Download failed ({resp.status}) for {media_url}")
            return False

        with open(out_path, "wb") as f:
            async for chunk in resp.content.iter_chunked(1 << 16):
                f.write(chunk)

    # Guard against truncated/empty downloads.
    if os.path.getsize(out_path) < 500:
        logger.warning(f"[cobalt] | Downloaded file too small, discarding: {out_path}")
        os.remove(out_path)
        return False

    return True


async def download_instagram_reel(url: str, download_dir: str, filename: str = None):  # type: ignore
    """
    Downloads Instagram reels via a self-hosted cobalt instance.

    Saves to ``{download_dir}/{filename or 'reel'}.mp4`` and returns True/False
    so existing callers keep working unchanged.

    :param url: Instagram reel URL
    :param download_dir: Directory to save the downloaded file
    :param filename: Optional custom filename (without extension)
    """
    os.makedirs(download_dir, exist_ok=True)
    out_path = os.path.join(download_dir, f"{filename or 'reel'}.mp4")

    try:
        async with semaphore:
            async with aiohttp.ClientSession(timeout=_COBALT_TIMEOUT) as session:
                media_url = await _resolve_cobalt_media(session, url)
                if not media_url:
                    return False

                if not await _stream_to_file(session, media_url, out_path):
                    return False

        logger.info(f"[Instagram:reel] | Successfully downloaded: {url}")
        return True
    except Exception as e:
        logger.exception(f"[Instagram:reel] | Error downloading {url}: {e}")
        if os.path.exists(out_path):
            os.remove(out_path)
        return False


def _ext_for_item(item: dict) -> str:
    """Pick a file extension for a cobalt media item.

    Videos/gifs -> .mp4 (handler treats only .mp4 as video); anything else is
    sent as a photo, so we keep the real image extension when known.
    """
    media_type = (item.get("type") or "").lower()
    if media_type in ("video", "gif"):
        return ".mp4"
    if media_type == "photo":
        return ".jpg"

    # Single-media posts: derive from cobalt's suggested filename.
    ext = os.path.splitext(item.get("filename") or "")[1].lower()
    if ext in (".mp4", ".mov", ".webm"):
        return ".mp4"
    return ext or ".jpg"


async def download_instagram_post(url: str, download_dir: str) -> list[str]:
    """
    Downloads an Instagram post (single media or carousel) via cobalt.

    Returns an ordered list of saved file paths (images and/or videos). An empty
    list means nothing could be downloaded. Files are named ``00``, ``01``, ...
    so directory order matches the post order.
    """
    os.makedirs(download_dir, exist_ok=True)
    saved: list[str] = []

    try:
        async with semaphore:
            async with aiohttp.ClientSession(timeout=_COBALT_TIMEOUT) as session:
                items = await _resolve_cobalt_post(session, url)
                for idx, item in enumerate(items):
                    out_path = os.path.join(download_dir, f"{idx:02d}{_ext_for_item(item)}")
                    if await _stream_to_file(session, item["url"], out_path):
                        saved.append(out_path)

        logger.info(f"[Instagram:post] | Downloaded {len(saved)} item(s) from {url}")
    except Exception as e:
        logger.exception(f"[Instagram:post] | Error downloading {url}: {e}")

    return saved


async def download_instagram_content(url: str, download_dir: str, filename: str = None):  # type: ignore
    """
    Smart downloader that detects content type and uses appropriate method.

    :param url: Instagram URL (post or reel)
    :param download_dir: Directory to save the downloaded file
    :param filename: Optional custom filename
    """
    # Check if it's a reel
    if "/reel/" in url or "/reels/" in url:
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
