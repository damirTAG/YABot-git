from aiograpi               import Client
from aiograpi.exceptions    import LoginRequired
from config                 import INST_USERNAME, INST_PASS

import logging

logger = logging.getLogger()
cl = Client()


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

# async def main():
#     await login_user()
#     link = "https://www.instagram.com/reel/DGYQXZOAciJ/?utm_source=ig_web_copy_link"
#     await get_video_direct_link(link)


# import asyncio
# asyncio.run(main())
