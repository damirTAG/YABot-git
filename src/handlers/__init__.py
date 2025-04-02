from aiogram import Dispatcher

from . import admin
from . import commands
from . import voice
from . import common
from . import media
from . import callbacks
from . import inline

def setup_routers(dp: Dispatcher):
    """Set up all handlers."""

    dp.include_router(admin.router)
    dp.include_router(commands.router)
    dp.include_router(voice.router)
    dp.include_router(common.router)
    dp.include_router(media.router)
    dp.include_router(callbacks.router)
    dp.include_router(inline.router)