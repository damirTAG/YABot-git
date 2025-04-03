import logging, time

from aiogram                import Router, types
from aiogram.filters        import Command, CommandStart, CommandObject
from aiogram.types          import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from random             import randrange

from utils              import Tools
from utils.decorators   import log
from services.openai    import generate_response
from database.repo      import DB_actions
from database.cache     import cache
from config.constants   import (
    HELP,
    INFO,
    CLOSE_BUTTON,
    GENERATING_BUTTON,
    FAILED_BUTTON,
    MAX_GPT_QUERY_LENGTH,
    IGNORE_CHAT_IDS
)

router  = Router()
db      = DB_actions()
logger  = logging.getLogger()
tools   = Tools()


# -- Base commands -- 

@router.message(CommandStart())
@log('start')
async def hello(message: types.Message):
    start_text = f"""
<b>Welcome! I will help you to download content from the list of services below:</b>

{HELP}
"""

    await message.reply(text=start_text, reply_markup=CLOSE_BUTTON)

@router.message(Command(commands=["roll", "ролл"], prefix="!/."))
@log('roll')
async def rate(message: types.Message):
    nick = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>"
    random = (randrange(101))
    roll = f'🎱 <b>{nick}</b> роллит! [1-100]. Выпадает: <b>{random}</b>!'
    await message.answer(
        text=roll, reply_to_message_id=message.message_id
    )

@router.message(Command(commands=['info', 'инфо'], prefix='!/.'))
@log('INFO')
async def info_handler(message: types.Message):    
    try:
        results = db.execute_query("SELECT video_link FROM video_cache", db_path='cache.db')
        video_links = [row[0] for row in results]
        total_files = len(video_links)

        platform_counts = tools.parse_platforms(video_links)
        sorted_platforms = sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)
        most_downloaded, most_downloaded_count = sorted_platforms.pop(0)

        others = "\n".join([f"• {platform}: {count:,} files" for platform, count in sorted_platforms])

        requests_stats = db.execute_query(""" 
            WITH daily_counts AS (
                SELECT DATE(used_at) as date, COUNT(*) as count
                FROM commands
                GROUP BY DATE(used_at)
            )
            SELECT 
                ROUND(AVG(count), 1) as avg_requests,
                MAX(count) as max_requests,
                DATE(MAX(date)) as last_active_date
            FROM daily_counts;
        """) or [(None, None, None)]
        if requests_stats and len(requests_stats) > 0:
            avg_requests, max_requests, last_active = requests_stats[0]
        else:
            avg_requests, max_requests, last_active = None, None, None

        avg_requests = avg_requests or 0
        max_requests = max_requests or 0

        ai_cur_stats = db.execute_query(""" 
            SELECT command, COUNT(*) as count
            FROM commands
            WHERE command IN ('ASK', 'CHATGPT', 'SPEECH_REC', 'COINS_CONVERTER')
            GROUP BY command
        """)
        feature_stats = dict(ai_cur_stats)

        ai_answers = feature_stats.get('ASK', 0) + feature_stats.get('CHATGPT', 0)
        speech_count = feature_stats.get('SPEECH_REC', 0)
        currency_conversions = feature_stats.get('COINS_CONVERTER', 0)

        total_users = db.execute_query("SELECT COUNT(DISTINCT user_id) FROM users")[0][0]
        total_chats = db.execute_query("SELECT COUNT(DISTINCT chat_id) FROM chats")[0][0]

        chats_info = f"and {total_chats:,} group chats "

        response = INFO.format(
            most_downloaded=most_downloaded,
            most_downloaded_count=most_downloaded_count,
            others=others,
            ai_answers=ai_answers,
            speech_count=speech_count,
            avg_requests=avg_requests,
            currency_conv=currency_conversions,
            total_files=total_files,
            total_users=total_users,
            chats_info=chats_info
        )

        await message.reply(response)

    except Exception as e:
        logger.error(f"Error in info_handler: {e}")
        await message.reply("Whoops! My stats calculator just did a backflip 🤸‍♂️ Try again in a bit! 😅")


@router.message(Command('ask'))
@log('ASK')
async def ask_handler(m: types.Message, command: CommandObject):
    query: str = command.args
    user = m.from_user

    if m.reply_to_message and not query:
        query = m.reply_to_message.text
    if not query:
        return await m.reply('Query is empty. Example use: <code>/ask whats the Pi number?</code>')
    if len(query) > MAX_GPT_QUERY_LENGTH:
        query = query[:MAX_GPT_QUERY_LENGTH].rstrip() + "..."

    temp_msg = await m.reply(
        f'{user.full_name} asking for: <code>{query}</code>',
        reply_markup=GENERATING_BUTTON
    )
    logger.info(f'{user.full_name} [{user.username}]: Asking for {query}')

    start_time = time.time()
    response = await generate_response(query)
    end_time = time.time()
    taken_time = round(end_time - start_time, 2)

    if response:
        await temp_msg.delete()
        resp_key = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f'✅ {taken_time} sec', callback_data='confirmed')]
            ]
        )
        await m.reply(
            f"{user.full_name} asked for: `{query}`\n\n*Answer:*\n{response}",
            reply_markup=resp_key,
            parse_mode='Markdown'
        )
    else:
        await temp_msg.delete()
        await m.reply(
            f'{user.full_name} asked for: <code>{query}</code>\n\n*Response failed =(*',
            reply_markup=FAILED_BUTTON,
            parse_mode='Markdown'
        )


# -- Music platforms search commands --
from services.yandexmusic   import YandexMusicSDK, TrackData
from services.soundcloud    import SoundCloudTool

sc = SoundCloudTool()

@router.message(Command('ym'))
@log('YM_TRACK_SEARCH')
async def ym_command_handler(message: types.Message, command: CommandObject):
    args: str = command.args
    if not args:
        return await message.reply("❌ Укажите поисковый запрос. Пример: <code>/ym The Beatles</code>")

    search_msg = await message.reply(f"<b>🔍 Searching:</b> <code>{args}</code>")
    async with YandexMusicSDK() as ym:
        results: list[TrackData] = await ym.search(args, count=10, download=False)
        if not results:
            return await search_msg.edit_text("🚫 Tracks not found =000")

        keyboard_builder = InlineKeyboardBuilder()
        
        for track in results:
            cache.add_to_cache("yandexmusic", track.id, track)
            
            keyboard_builder.button(
                text=f"{track.title} - {track.artists}", 
                callback_data=f"yandex_{track.id}"
            )
        
        keyboard_builder.button(
            text='❌ Close',
            callback_data='close'
        )
        keyboard_builder.adjust(1)
        await search_msg.delete()
        await message.reply(f'<b>{args.capitalize()}</b>', reply_markup=keyboard_builder.as_markup())


@router.message(Command('sc'))
@log('SC_TRACK_SEARCH')
async def soundsearch(message: types.Message, command: CommandObject):
    chat_id = message.chat.id
    if chat_id in IGNORE_CHAT_IDS:
        return False

    args = command.args
    if not args:
        return await message.reply("❌ Укажите поисковый запрос. Пример: <code>/sc virtual love</code>")

    if tools.check_query(args) == False:
        return await message.reply('Search query is too long!')

    search_msg = await message.reply(f"<b>🔍 Searching:</b> <code>{args}</code>")

    try:
        results = await sc.search_tracks(args)

        if not results:
            return await search_msg.edit_text("🚫 Tracks not found =000")

        keyboard_builder = InlineKeyboardBuilder()

        for track in results:
            if not track.download_link:
                continue 

            cache.add_to_cache("soundcloud", track.track_id, track)

            keyboard_builder.button(
                text=f"{track.title} - {track.artists}",
                callback_data=f"soundcl_{track.track_id}"
            )

        keyboard_builder.button(text="❌ Close", callback_data="close")
        keyboard_builder.adjust(1)

        await search_msg.delete()
        await message.reply(f'<b>{args.capitalize()}</b>', reply_markup=keyboard_builder.as_markup())

    except Exception as e:
        logger.error(f"SoundCloud search error: {e}")