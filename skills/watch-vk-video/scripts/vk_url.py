"""Нормализация ссылок на ВК Видео. Без сети — чтобы покрывалось тестами."""
import re
from urllib.parse import parse_qs, unquote, urlsplit

# vkvideo.ru — новый домен, vk.com/vk.ru/vkontakte.ru — старые
HOSTS = {"vk.com", "vkvideo.ru", "vk.ru", "vkontakte.ru"}

# video-226836549_456240037 / clip-1_2 / video123456_456239017 в любом месте ссылки
_ID_RE = re.compile(r"(?:^|[/?&=])(video|clip)(-?\d+)_(\d+)\b")


class VkUrlError(ValueError):
    """Ссылка не похожа на ВК Видео."""


def _host(url):
    netloc = urlsplit(url if "//" in url else "//" + url).netloc.lower()
    host = netloc.rsplit("@", 1)[-1].split(":")[0]
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


def parse_vk_url(url):
    """-> {"owner_id": int, "video_id": int, "canonical": str, "kind": "video"|"clip"}

    owner_id < 0 — сообщество, > 0 — пользователь.
    f"{owner_id}_{video_id}" одновременно служит ключом кэша.
    """
    if not isinstance(url, str) or not url.strip():
        raise VkUrlError(
            "Пустая ссылка. Нужна ссылка вида https://vkvideo.ru/video-226836549_456240037"
        )

    raw = unquote(url.strip())
    host = _host(raw)
    if host not in HOSTS:
        raise VkUrlError(
            f"Это не ссылка на ВК Видео (домен: {host or 'не распознан'}). "
            "Жду vkvideo.ru или vk.com — например https://vkvideo.ru/video-226836549_456240037"
        )

    match = _ID_RE.search(raw)
    if match:
        kind, owner_id, video_id = match.group(1), int(match.group(2)), int(match.group(3))
    else:
        # embed-плеер: video_ext.php?oid=-226836549&id=456240037&hash=...
        query = parse_qs(urlsplit(raw).query)
        oid, vid = query.get("oid", [None])[0], query.get("id", [None])[0]
        try:
            owner_id, video_id, kind = int(oid), int(vid), "video"
        except (TypeError, ValueError):
            raise VkUrlError(
                f"Не нашёл идентификатор видео в ссылке: {url}\n"
                "Жду что-то вроде https://vkvideo.ru/video-226836549_456240037"
            ) from None

    return {
        "owner_id": owner_id,
        "video_id": video_id,
        "canonical": f"https://vkvideo.ru/video{owner_id}_{video_id}",
        "kind": kind,
    }
