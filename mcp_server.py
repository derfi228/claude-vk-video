#!/usr/bin/env python3
"""MCP-сервер: тот же пайплайн, но для обычного чата Claude Desktop.

В обычном чате скиллы выполняются в облачной песочнице Anthropic — там нет ни
твоего ffmpeg, ни доступа к ВК. А MCP-серверы Desktop запускает локально, на
твоей машине. Поэтому здесь второй вход в тот же vk_fetch.py: чат зовёт tool,
tool качает и разбирает ролик локально и отдаёт обратно текст и кадры.

Прописывается в claude_desktop_config.json, раздел mcpServers.
"""
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import ImageContent, TextContent

FETCH = Path(__file__).resolve().parent / "skills" / "watch-vk-video" / "scripts" / "vk_fetch.py"
TRANSCRIPT_LIMIT = 20000  # символов: дальше тащить в чат бессмысленно, есть файл

# Куки браузера — не то, что модель должна решать читать сама, начитавшись
# транскрипта. В CLI флаг набирает человек, здесь его запрашивает чат, поэтому
# нужен явный опт-ин хозяина машины.
COOKIES_ALLOWED = os.environ.get("VK_VIDEO_ALLOW_COOKIES") == "1"
COOKIES_REFUSED = (
    "Чтение кук браузера выключено. Если это ваше решение, добавьте серверу "
    '"env": {"VK_VIDEO_ALLOW_COOKIES": "1"} в claude_desktop_config.json и '
    "перезапустите Desktop. Без кук закрытые и 18+ ролики не скачать."
)

server = MCPServer(
    "vk-video",
    instructions="Разбор видео с ВК (vkvideo.ru, vk.com): транскрипт с таймкодами и кадры.",
)


def mmss(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 60}:{seconds % 60:02d}"


@server.tool(
    description=(
        "Скачать видео с ВК Видео (vkvideo.ru / vk.com / vk.ru) и вернуть его содержимое: "
        "название, автора, длительность, транскрипт с таймкодами и кадры картинками. "
        "Работает со страницей видео, клипом, embed-ссылкой, ссылкой из плейлиста или со стены. "
        "Первый вызов на длинном ролике идёт минуты (скачивание + распознавание речи); "
        "результат кэшируется, поэтому повторный вызов по той же ссылке отвечает сразу."
    )
)
def analyze_vk_video(
    url: str,
    max_frames: int = 6,
    whisper_model: str = "small",
    no_transcribe: bool = False,
    cookies_from_browser: str = "",
) -> list:
    """url — ссылка на ролик. max_frames — сколько кадров вернуть картинками (6 по умолчанию,
    каждый кадр дорог по контексту). whisper_model — tiny/base/small/medium/large-v3.
    cookies_from_browser — chrome/firefox/edge для закрытых и 18+ видео; работает,
    только если хозяин машины разрешил это переменной VK_VIDEO_ALLOW_COOKIES=1."""
    cmd = [sys.executable, str(FETCH), url,
           "--max-frames", str(max_frames), "--whisper-model", whisper_model]
    if no_transcribe:
        cmd.append("--no-transcribe")
    if cookies_from_browser:
        if not COOKIES_ALLOWED:
            return [TextContent(type="text", text=COOKIES_REFUSED)]
        cmd += ["--cookies-from-browser", cookies_from_browser]

    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        tail = (proc.stderr or proc.stdout or "")[-1500:]
        return [TextContent(type="text", text=f"vk_fetch не вернул JSON:\n{tail}")]

    if not data.get("ok"):
        return [TextContent(type="text",
                            text=f"[{data.get('error_code')}] {data.get('message')}")]

    lines = [
        f"«{data['title']}» — {data['uploader']}",
        f"длительность {mmss(data['duration'])}, загружено {data['upload_date'] or '?'}",
        f"ссылка: {data['url']}",
        f"файлы: {data['cache_dir']}",
    ]
    if data.get("description"):
        lines.append(f"описание: {data['description'][:500]}")
    for warning in data.get("warnings") or []:
        lines.append(f"! {warning}")

    if data.get("transcript_txt") and Path(data["transcript_txt"]).exists():
        text = Path(data["transcript_txt"]).read_text("utf-8")
        cut = " …обрезано, полный текст в transcript.txt" if len(text) > TRANSCRIPT_LIMIT else ""
        lines += ["", "ТРАНСКРИПТ" + cut, text[:TRANSCRIPT_LIMIT]]
    else:
        lines += ["", "Транскрипта нет — смотри кадры и предупреждения выше."]

    shots = data.get("frames") or []
    if shots:
        lines += ["", "КАДРЫ (в порядке ниже): " +
                  ", ".join(f"{mmss(f['t'])}{'*' if f.get('scene') else ''}" for f in shots),
                  "* — смена сцены (слайд, склейка, новый экран)"]

    out = [TextContent(type="text", text="\n".join(lines))]
    for frame in shots:
        path = Path(frame["path"])
        if path.exists():
            out.append(ImageContent(type="image", mime_type="image/jpeg",
                                    data=base64.b64encode(path.read_bytes()).decode()))
    return out


if __name__ == "__main__":
    server.run(transport="stdio")
