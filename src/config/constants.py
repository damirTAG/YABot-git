GH_REPO: str    = "https://github.com/damirTAG/YABot-git"
# -- IDS -- 
DAMIR_USER_ID   = 1038468423
CACHE_CHAT      = -1001911592881
IGNORE_CHAT_IDS = [-1001559555304, -1001919227306, -1001987624296, -1002050266275]   
# -1001559555304, -1001919227306, -1001987624296

# -- UI TEXT --
SAVED           = "🔥 This {} saved. Call @yerzhanakh_bot in inline to send it in any chat"
BASE_ERROR      = f"<i>Sorry, failed to proceed this request</i>"
UPDATE_NOTIFY   = "Youtube Video/Shorts downloader is now working! Audio handler will be added soonly\nЮтуб видео и шортсы тепер снова качает, позже добавлю загрузку видео"
HELP            = """<b>Supporting services:</b>
<i>🔵 Instagram Reels/Posts
🔵 VK Clips
🟣 Twitch Clips
⚫️ TikTok Videos/Pics
🟠 SoundCloud Search/Track
🟡 Yandex.Music Search/Track (New)</i>
<s>🔴 YouTube Video/Shorts</s>

<b>Inline:</b>
<code>@yerzhanakh_bot</code> - get your saved tracks
<code>@yerzhanakh_bot ask ...</code> - ask something to AI

<b>Commands:</b>
<code>/ym [query]</code> — search tracks from YandexMusic
<code>/sc [query]</code> — search tracks from SoundCloud
<code>/roll</code> — roll number between 1 and 100 (like in dota)
<code>/ask your_message</code> — ask something to AI, 
    - or reply with this command to someones message

<b>Features:</b>
🎤 <i>Voice recognizer</i> (works in groups), recognizes voice and sends text of recognized audio.
🪙 <i>Coins Converter</i> converts crypto and fiat currencies instantly! 
Example usage: <code>1 SOL</code> | <code>50 TON RUB</code> | <code>50 USD KZT</code>
"""
INFO            = (
    "📊 Hey there! Here are the current stats:\n\n"
    "🔥 {most_downloaded} is the most popular source with {most_downloaded_count:,} downloads\n\n"
    "Downloads from other platforms:\n"
    "{others}\n\n"
    "🤖 Delivered more than {ai_answers:,} answers from AI and recognized almost {speech_count:,} voice messages\n\n"
    "💫 Additional stats:\n"
    "• Processing about {avg_requests:,} requests daily\n"
    "• Performed {currency_conv:,} currency conversions\n"
    "• Total files delivered: {total_files:,}\n"
    "• Currently serving {total_users:,} users {chats_info}\n\n"
    "❤️ Thanks for using the bot! Any suggestions? Feel free to contact @damirtag"
    f"\n\n<i>Bot's source-code available on</i> <b><a href='{GH_REPO}'>GitHub</a></b>"
)
ARE_YOU_SURE_STICKER_ID = 'CAACAgIAAxkBAAIH22geNVJr-3S_AjeP6c66NFrUu-5OAAI1dwAC7cXxSlIE1lAabmYFNgQ'

# -- VARS -- 
MAX_GPT_QUERY_LENGTH: int = 150
ADMIN_USERS_PER_PAGE: int = 10
CHATGPT_ROLE: str = """
Ты встроен в Ержан бота в Телеграме, твой создатель - Дамир. Ты помощник AI ассистент.\n
Можно обращаться на 'ты' и шутить но не всегда, если понимаешь что\n
вопрос серьезный то отвечай серьезно. Будь иногда дерзким. В ответах с кодом можно слегка токсичить.\n
Поддерживай многоязычность, отвечай на том языке на котором задан вопрос
"""
COOL_PHRASES = [
    "Работа не волк, а волком быть не хочется.",
    "Утро вечера мудренее, особенно после обеда.",
    "Кто рано встает, тот весь день хочет спать.",
    "Без труда не вытащишь и рыбку из интернета.",
    "Семь раз отмерь, один раз забудь.",
    "Делу время, а кофе — всегда.",
    "Работа не волк, в лес не убежит, но и сама не сделается.",
    "Не откладывай на завтра то, что можно отменить.",
    "Терпение и труд всё перетрут, особенно нервы.",
    "Глаза боятся, а руки в карманах.",
    "Не имей сто рублей, а имей сто друзей с машинами.",
    "Лучше поздно, чем никогда, но лучше вовремя.",
    "Семь пятниц на неделе — мечта прокрастинатора.",
    "Работа дураков любит, но платит умным.",
    "Не всё коту масленица, иногда и диета.",
    "Любишь кататься — люби и санки в кредит.",
    "Без кота и жизнь не та, а с котом — шерсть везде.",
    "Денег нет, но вы держитесь, особенно за стул.",
    "Не откладывай на завтра то, что можно съесть сегодня.",
    "Работа не волк, но и отдыхать не даёт.",
    "Ждём, как зарплату в конце месяца...",
    "Подождём, но недолго!",
    "Где наша скорость? Где наша реакция?",
    "Ожидание – это тоже процесс!",
    "Терпение и труд, всё ещё ждут...",
    "Технологии будущего требуют времени!",
    "Боты тоже могут тормозить, но с душой!",
    "Не спеши, а то будет как в прошлый раз!",
    "Делу час потехехехехе",
    "тыквенные семечки",
    "ваш iq: 7",
    "эээ блютуз кто такой",
    "фимоз",
    "а мне мощные сиське дороже родины",
    "это в жизни ты дохуя смелый, а в инете смож меня уделать?"
]


# -- BUTTONS --
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SAVE_BUTTON             = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Save", callback_data="save")]
])

SAVED_BUTTON            = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Saved", callback_data="save")]
    ]
)

CLOSE_BUTTON            = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Close", callback_data="close")]
])

ADMIN_KEYBOARD          = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_admin")],
    [InlineKeyboardButton(text="👥 View All Users", callback_data="view_users:0")]
])

GENERATING_BUTTON       = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='⏳ Generating...', callback_data='waiting')]
])

FAILED_BUTTON           = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='❌ Failed', callback_data='failed')]
])

PM_BUTTON               = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Open PM', url='https://t.me/yerzhanakh_bot')]
])