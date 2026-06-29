"""Cobalt response parsing — the core of the Instagram download path.

These exercise the status handling (tunnel/redirect/picker/error/unknown) and
the extension picker without touching the network: ``_cobalt_request`` is
monkeypatched to return canned API payloads.
"""

import pytest

from services import inst


@pytest.fixture
def patch_request(monkeypatch):
    """Make ``inst._cobalt_request`` return a fixed payload."""

    def _apply(payload):
        async def _fake(session, url):
            return payload

        monkeypatch.setattr(inst, "_cobalt_request", _fake)

    return _apply


# --- _resolve_cobalt_media (single video, used for reels) ---


@pytest.mark.parametrize("status", ["tunnel", "redirect"])
async def test_resolve_media_direct(patch_request, status):
    patch_request({"status": status, "url": "https://cobalt/v.mp4"})
    assert await inst._resolve_cobalt_media(None, "u") == "https://cobalt/v.mp4"


async def test_resolve_media_picker_prefers_video(patch_request):
    patch_request(
        {
            "status": "picker",
            "picker": [
                {"type": "photo", "url": "p1"},
                {"type": "video", "url": "v1"},
            ],
        }
    )
    assert await inst._resolve_cobalt_media(None, "u") == "v1"


async def test_resolve_media_picker_falls_back_to_first(patch_request):
    patch_request({"status": "picker", "picker": [{"type": "photo", "url": "p1"}]})
    assert await inst._resolve_cobalt_media(None, "u") == "p1"


@pytest.mark.parametrize("payload", [{"status": "error", "error": {"code": "x"}}, {"status": "??"}])
async def test_resolve_media_failure_returns_none(patch_request, payload):
    patch_request(payload)
    assert await inst._resolve_cobalt_media(None, "u") is None


# --- _resolve_cobalt_post (single + carousel) ---


async def test_resolve_post_single(patch_request):
    patch_request({"status": "redirect", "url": "u1", "filename": "a.jpg"})
    items = await inst._resolve_cobalt_post(None, "u")
    assert len(items) == 1
    assert items[0]["url"] == "u1"


async def test_resolve_post_picker_keeps_order_and_filters_urlless(patch_request):
    patch_request(
        {
            "status": "picker",
            "picker": [
                {"type": "photo", "url": "p1"},
                {"type": "video", "url": "v1"},
                {"type": "photo"},  # no url -> dropped
            ],
        }
    )
    items = await inst._resolve_cobalt_post(None, "u")
    assert [i["url"] for i in items] == ["p1", "v1"]


async def test_resolve_post_error_returns_empty(patch_request):
    patch_request({"status": "error", "error": {}})
    assert await inst._resolve_cobalt_post(None, "u") == []


# --- _ext_for_item ---


@pytest.mark.parametrize(
    "item, expected",
    [
        ({"type": "video"}, ".mp4"),
        ({"type": "gif"}, ".mp4"),
        ({"type": "photo"}, ".jpg"),
        ({"type": None, "filename": "clip.mp4"}, ".mp4"),
        ({"type": None, "filename": "clip.mov"}, ".mp4"),
        ({"type": None, "filename": "pic.jpg"}, ".jpg"),
        ({"type": None, "filename": "pic.png"}, ".png"),
        ({"type": None, "filename": ""}, ".jpg"),
    ],
)
def test_ext_for_item(item, expected):
    assert inst._ext_for_item(item) == expected
