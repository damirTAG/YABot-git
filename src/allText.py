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
<s>🔴 YouTube Video/Shorts/Music</s>
</i>

<b>Commands:</b>
<code>/ym [query]</code> — search tracks from YandexMusic
<code>/sc [query]</code> — search tracks from SoundCloud
<code>/roll</code> — roll number between 1 and 100 (like in dota)

<b>Features:</b>
🎤 <i>Voice recognizer</i> (works in groups), recognizes voice and sends text of recognized audio.
"""
update_txt = ""

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
