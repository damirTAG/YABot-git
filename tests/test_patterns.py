"""Link-detection regexes — these gate which handler fires for a given URL."""

import pytest

from config.enums import Patterns


@pytest.mark.parametrize(
    "url",
    [
        "https://www.tiktok.com/@user/video/7367017049136172320",
        "https://vm.tiktok.com/ZMabc123/",
        "https://vt.tiktok.com/ZSabc123/",
    ],
)
def test_tiktok_matches(url):
    assert Patterns.TIKTOK.value.match(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/reel/ABC123/",
        "https://www.youtube.com/watch?v=abcdefghijk",
        "not a link at all",
    ],
)
def test_tiktok_rejects_non_tiktok(url):
    assert not Patterns.TIKTOK.value.match(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/reel/ABC123/",
        "https://instagram.com/reels/ABC123/",
        "https://www.instagram.com/share/XYZ789/",
        "https://www.instagram.com/tv/ABC123/",
    ],
)
def test_reels_matches(url):
    assert Patterns.INST_REELS.value.match(url)


def test_reels_excludes_posts():
    # /p/ posts must NOT be offered to the single-video reel/inline path.
    assert not Patterns.INST_REELS.value.match("https://www.instagram.com/p/ABC123/")


def test_posts_matches_p_links():
    assert Patterns.INST_POSTS.value.match("https://www.instagram.com/p/ABC123/")


def test_posts_excludes_reels():
    assert not Patterns.INST_POSTS.value.match("https://www.instagram.com/reel/ABC123/")
