"""Single-video dispatch — routes a raw link to the right platform downloader.

The per-platform helpers (which hit the network) are monkeypatched; we only
assert the routing decision and the unsupported-link guard.
"""

import pytest

from services import downloader


@pytest.fixture
def patch_helpers(monkeypatch):
    calls = {}

    async def fake_tiktok(link, download_dir):
        calls["tiktok"] = link
        return "tiktok.mp4"

    async def fake_reel(link, download_dir):
        calls["reel"] = link
        return "reel.mp4"

    monkeypatch.setattr(downloader, "_download_tiktok_video", fake_tiktok)
    monkeypatch.setattr(downloader, "_download_reel", fake_reel)
    return calls


async def test_routes_tiktok(patch_helpers, tmp_path):
    out = await downloader.download_single_video("https://www.tiktok.com/@u/video/1", str(tmp_path))
    assert out == "tiktok.mp4"
    assert "tiktok" in patch_helpers
    assert "reel" not in patch_helpers


async def test_routes_reel(patch_helpers, tmp_path):
    out = await downloader.download_single_video(
        "https://www.instagram.com/reel/ABC123/", str(tmp_path)
    )
    assert out == "reel.mp4"
    assert "reel" in patch_helpers
    assert "tiktok" not in patch_helpers


async def test_unsupported_link_returns_none(patch_helpers, tmp_path):
    out = await downloader.download_single_video("https://example.com/whatever", str(tmp_path))
    assert out is None
    assert patch_helpers == {}


@pytest.fixture
def patch_resolvers(monkeypatch):
    calls = {}

    async def fake_tiktok(link):
        calls["tiktok"] = link
        return [{"type": "video", "url": "tt", "thumb": "ttc"}]

    async def fake_instagram(link):
        calls["instagram"] = link
        return [{"type": "video", "url": "ig", "thumb": "ig"}]

    monkeypatch.setattr(downloader, "_resolve_tiktok_inline", fake_tiktok)
    monkeypatch.setattr(downloader, "_resolve_instagram_inline", fake_instagram)
    return calls


async def test_resolve_inline_routes_tiktok(patch_resolvers):
    out = await downloader.resolve_inline_media("https://www.tiktok.com/@u/video/1")
    assert out == [{"type": "video", "url": "tt", "thumb": "ttc"}]
    assert "tiktok" in patch_resolvers


async def test_resolve_inline_routes_reel(patch_resolvers):
    out = await downloader.resolve_inline_media("https://www.instagram.com/reel/ABC123/")
    assert out == [{"type": "video", "url": "ig", "thumb": "ig"}]
    assert "instagram" in patch_resolvers


async def test_resolve_inline_unsupported_returns_empty(patch_resolvers):
    out = await downloader.resolve_inline_media("https://example.com/whatever")
    assert out == []
    assert patch_resolvers == {}
