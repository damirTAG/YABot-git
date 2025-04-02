from aiograpi               import Client
from aiograpi.exceptions    import LoginRequired
from config                 import INST_USERNAME, INST_PASS
from urllib.parse           import urlparse, unquote
from tqdm.asyncio           import tqdm

import logging, aiohttp, asyncio
import os


logger = logging.getLogger()
cl = Client()
semaphore = asyncio.Semaphore(20)


async def login_user():
    """
    Attempts to login to Instagram using either the provided session information
    or the provided username and password.
    """
    session = cl.load_settings("session.json")

    login_via_session = False
    login_via_pw = False

    if session:
        try:
            cl.set_settings(session)
            await cl.login(INST_USERNAME, INST_PASS)

            # check if session is valid
            try:
                await cl.get_timeline_feed()
            except LoginRequired:
                logger.info("Session is invalid, need to login via username and password")

                old_session = cl.get_settings()

                # use the same device uuids across logins
                cl.set_settings({})
                cl.set_uuids(old_session["uuids"])

                await cl.login(INST_USERNAME, INST_PASS)
            login_via_session = True
        except Exception as e:
            logger.info("Couldn't login user using session information: %s" % e)

    if not login_via_session:
        try:
            logger.info("Attempting to login via INST_USERNAME and password. username: %s" % INST_USERNAME)
            if await cl.login(INST_USERNAME, INST_PASS):
                login_via_pw = True
        except Exception as e:
            logger.info("Couldn't login user using username and password: %s" % e)

    if not login_via_pw and not login_via_session:
        raise Exception("Couldn't login user with either password or session")
    
async def get_video_direct_link(link: str) -> str:
    media_pk = await cl.media_pk_from_url(link)

    video_url = (await cl.media_info(media_pk)).video_url
    return video_url

async def download_inst_post(session: aiohttp.ClientSession, url, download_dir):
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

DEFAULT_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7,kk;q=0.6",
    "cache-control": "max-age=0",
    "priority": "u=0, i",
    "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "cross-site",
    "sec-fetch-user": "?1",
    "sec-gpc": "1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}

async def download_video(url: str, video_filename: str, headers: dict = None):
    """
    Асинхронная функция для скачивания видео.

    :param url: URL видео для скачивания.
    :param video_filename: Путь для сохранения файла.
    :param headers: Заголовки HTTP-запроса (по умолчанию используется DEFAULT_HEADERS).
    """
    headers = headers or DEFAULT_HEADERS

    if os.path.exists(video_filename):
        logger.info(f"[Instagram:video] | {video_filename} уже существует. Пропускаем скачивание.")
        return

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"[Instagram:video] | Ошибка {response.status} при загрузке {url}")
                    return

                total_size = int(response.headers.get("content-length", 0))
                
                # Запись видео с прогресс-баром
                with open(video_filename, "wb") as file, tqdm(
                    total=total_size, unit="B", unit_scale=True, desc=video_filename
                ) as pbar:
                    async for chunk in response.content.iter_any():
                        file.write(chunk)
                        pbar.update(len(chunk))

                logger.info(f"[Instagram:video] | Загружено и сохранено как {video_filename}")

    except Exception as e:
        logger.exception(f"[Instagram:video] | Ошибка при скачивании {url}: {e}")

# async def main():
#     await login_user()
#     link = "https://www.instagram.com/reel/DGYQXZOAciJ/?utm_source=ig_web_copy_link"
#     await get_video_direct_link(link)


# import asyncio
# asyncio.run(main())
