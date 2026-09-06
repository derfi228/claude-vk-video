"""pytest tests/ — или просто `python tests/test_vk_url.py`, если pytest не стоит."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "watch-vk-video" / "scripts"))

from vk_url import VkUrlError, parse_vk_url  # noqa: E402

OK = [
    # (ссылка, owner_id, video_id, kind)
    ("https://vkvideo.ru/video-226836549_456240037", -226836549, 456240037, "video"),
    ("https://vk.com/video-226836549_456240037", -226836549, 456240037, "video"),
    ("https://vk.com/video123456_456239017", 123456, 456239017, "video"),
    ("https://vk.com/video_ext.php?oid=-226836549&id=456240037&hash=abc123", -226836549, 456240037, "video"),
    ("https://vkvideo.ru/playlist/-226836549_5/video-226836549_456240037", -226836549, 456240037, "video"),
    ("https://vk.com/wall-123_456?z=video-226836549_456240037%2Fpl_post_-123_456", -226836549, 456240037, "video"),
    ("https://vk.com/clip-226836549_456240037", -226836549, 456240037, "clip"),
    ("https://vkvideo.ru/video-226836549_456240037?t=125", -226836549, 456240037, "video"),
    ("https://vkvideo.ru/video-226836549_456240037?utm_source=tg&utm_medium=post", -226836549, 456240037, "video"),
    ("https://m.vk.com/video-226836549_456240037", -226836549, 456240037, "video"),
    ("vk.com/video-226836549_456240037", -226836549, 456240037, "video"),
]

BAD = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://vk.com/video-226836549",  # битая: нет video_id
    "просто текст",
    "",
]


def test_supported_urls():
    for url, owner_id, video_id, kind in OK:
        got = parse_vk_url(url)
        assert got["owner_id"] == owner_id, url
        assert got["video_id"] == video_id, url
        assert got["kind"] == kind, url


def test_canonical_form():
    for url, owner_id, video_id, _ in OK:
        assert parse_vk_url(url)["canonical"] == f"https://vkvideo.ru/video{owner_id}_{video_id}"


def test_garbage_raises():
    for url in BAD:
        try:
            parse_vk_url(url)
        except VkUrlError:
            continue
        raise AssertionError(f"должно было упасть: {url!r}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
