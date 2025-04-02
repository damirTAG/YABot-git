from enum import Enum
import re

class Patterns(Enum):
    TIKTOK = re.compile(r"https?://(?:www\.)?(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)/.*")
    SOUNDCLOUD = re.compile(r"https?://(?:www\.)?soundcloud\.com/[^\s]+")
    YANDEX_MUSIC = re.compile(r"https://music\.yandex\.(?:ru|com|kz)/album/\d+/track/\d+")
    YOUTUBE = re.compile(
        r"(?:https?:\/\/)?(?:www\.)?"
        r"(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)"
        r"([\w-]{11})"
    )
    TWITCH_VK = re.compile(r"(?:https?://)?(?:www\.)?(?:vk\.com/clip|twitch\.tv/)")
    INST_POSTS = re.compile(r"(https?://)?(www\.)?instagram\.com/p/.*")
    INST_REELS = re.compile(r"(https?://)?(www\.)?instagram\.com/(reel|share|tv)/.*")