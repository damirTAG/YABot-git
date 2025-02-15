start_txt = "Hi! This is multifunctional bot, press /help"
text_txt = "In what type to download?"
error_txt = f'<i>Error while sending content</i>'
help_txt = """
<b>Supporting services:</b>
<i>🔵 Instagram Reels/Posts
🔵 VK Clips
🟣 Twitch Clips
⚫️ TikTok Videos/Pics
🟠 SoundCloud Search/Track
🟡 Yandex.Music Search/Track (New)

Unavailable:
<s>🔴 YouTube Video/Shorts/Music</s></i>

<b>Inline:</b>
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
update_txt = ""
cool_phrases = [
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

class YANDEX_MUSIC_TRACK_CAPTION:
    def __init__(self, track):
        self.track = track

    def format(self) -> str:
        return (
            f"<b>🎵 Track:</b> <a href='https://music.yandex.com/album/{self.track.album_id}/track/{self.track.id}'>"
            f"{self.track.title}</a> • {self.track.year}\n"
            f"<b>👥 Artists:</b> <i>{self.track.artists}</i>\n"
            f"<b>📀 Album:</b> <a href='https://music.yandex.com/album/{self.track.album_id}'>"
            f"{self.track.album_title}</a>\n"
            f"<b>🎶 Genre:</b> <i>{self.track.genre.capitalize()}</i>\n"
            f"<b>⏱️ Duration:</b> <code>{int(self.track.duration // 60)}:{int(self.track.duration % 60):02d}</code>"
        )
