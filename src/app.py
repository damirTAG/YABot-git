import asyncio

from aiogram                import Bot, Dispatcher
from aiogram.enums          import ParseMode
from aiogram.client.default import DefaultBotProperties

from config                 import ACTIVE_BOT_TOKEN, logger
from handlers               import setup_routers
from database.repo          import DB_actions
from services.coins         import init_coins_apis


async def main():
    # Initialize bot and dispatcher
    bot = Bot(
        token=ACTIVE_BOT_TOKEN, 
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            allow_sending_without_reply=True
        )
    )
    dp = Dispatcher()
    
    # Initialize database
    DB_actions().init_db()
    logger.info("Database initialized")
    
    # Set up all routers
    setup_routers(dp)
    logger.info("Initializing coins data...")
    await init_coins_apis()
    
    # Log bot startup
    logger.info("Starting bot...")
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)