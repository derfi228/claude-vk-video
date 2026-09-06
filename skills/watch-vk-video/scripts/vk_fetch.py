#!/usr/bin/env python3
"""ВК Видео -> видео, аудио, транскрипт, кадры.

На stdout — только JSON. Прогресс и предупреждения — в stderr.
"""
import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frames  # noqa: E402
from vk_url import VkUrlError, parse_vk_url  # noqa: E402

for stream in (sys.stdout, sys.stderr):  # Windows-консоль иначе давится кириллицей
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

CACHE_ROOT = Path.home() / ".cache" / "vk-video"

FFMPEG_HINT = (
    "Не найден ffmpeg — без него нельзя ни достать звук, ни нарезать кадры.\n"
    "  Windows: winget install Gyan.FFmpeg   (или choco install ffmpeg)\n"
    "  macOS:   brew install ffmpeg\n"
    "  Linux:   sudo apt install ffmpeg   /   sudo dnf install ffmpeg\n"
    "После установки открой новый терминал, чтобы ffmpeg попал в PATH."
)
WHISPER_HINT = (
    "faster-whisper не установлен, транскрипт пропущен. Установи: pip install faster-whisper"
)


class Fail(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def tail(text, n=6):
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    errors = [ln for ln in lines if "ERROR" in ln or "error" in ln]
    return "\n".join((errors or lines)[:n])


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


@lru_cache(maxsize=None)
def ytdlp_cmd():
    """Тот же интерпретатор, что и скрипт; иначе — бинарник из PATH."""
    if importlib.util.find_spec("yt_dlp"):
        cmd = [sys.executable, "-m", "yt_dlp"]
    elif shutil.which("yt-dlp"):
        cmd = [shutil.which("yt-dlp")]
    else:
        raise Fail("no_ytdlp", "Не найден yt-dlp. Установи: pip install -U yt-dlp")

    version = run(cmd + ["--version"]).stdout.strip()
    found = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", version)
    if found:
        age = (date.today() - date(*map(int, found.groups()))).days
        if age > 30:
            log(f"! yt-dlp {version} — версии {age} дней. ВК регулярно ломает извлечение, "
                "обнови: pip install -U yt-dlp")
    return cmd


def classify(stderr):
    """Текст ошибки yt-dlp -> (error_code, что делать человеку)."""
    low = (stderr or "").lower()
    if "unable to extract" in low or "player params" in low or "extractorerror" in low:
        return "extractor_broken", (
            "ВК поменял отдачу видео, yt-dlp не смог разобрать страницу.\n"
            "1) Обнови экстрактор: pip install -U yt-dlp\n"
            "2) Если не помогло — посмотри открытые баги: "
            "https://github.com/yt-dlp/yt-dlp/issues?q=is%3Aissue+vk\n"
            f"Исходная ошибка:\n{tail(stderr)}")
    auth_markers = ("private", "closed group", "only available", "sign in", "log in",
                    "authoriz", "18+", "age-restrict", "age restrict", "restricted",
                    "access denied", "not available in your", "недоступ", "закрыт")
    if any(marker in low for marker in auth_markers):
        return "auth_required", (
            "Видео закрыто: приватное, 18+, в закрытом сообществе или заблокировано в регионе.\n"
            "Единственный способ — отдать куки браузера, где ты залогинен в ВК:\n"
            "  --cookies-from-browser chrome   (firefox, edge, yandex, ...)\n"
            f"Исходная ошибка:\n{tail(stderr)}")
    return "unknown", f"yt-dlp не справился:\n{tail(stderr)}"


def ytdlp_base(cookies):
    flags = ["--no-playlist", "--no-warnings"]
    if cookies:
        flags += ["--cookies-from-browser", cookies]
    return flags


def fetch_meta(url, cookies):
    log("метаданные…")
    proc = run(ytdlp_cmd() + ytdlp_base(cookies) + ["--dump-single-json", "--skip-download", url])
    if proc.returncode != 0:
        raise Fail(*classify(proc.stderr))
    try:
        raw = json.loads(proc.stdout)
    except ValueError:
        raise Fail("unknown",
                   "yt-dlp вернул не-JSON:\n" + tail(proc.stdout + proc.stderr)) from None
    return {
        "title": raw.get("title") or "",
        "uploader": raw.get("uploader") or raw.get("channel") or raw.get("uploader_id") or "",
        "duration": int(raw.get("duration") or 0),
        "upload_date": raw.get("upload_date") or "",
        "description": raw.get("description") or "",
    }


def download(url, cookies, max_height, cache):
    # нам нужны кадры и звук, а не 1080p
    fmt = (f"bv*[height<={max_height}]+ba/b[height<={max_height}]"
           f"/bv*[height<={max_height}]/wv*+ba/w")
    log(f"скачиваю (<= {max_height}p)…")
    try:  # прогресс yt-dlp пишем в stderr, stdout священен
        progress = sys.stderr.fileno()
    except (AttributeError, OSError):
        progress = subprocess.DEVNULL
    proc = subprocess.run(
        ytdlp_cmd() + ytdlp_base(cookies) +
        ["-f", fmt, "--merge-output-format", "mp4", "--newline",
         "-N", "4",  # длинные ролики ВК отдаёт кусками HLS, в один поток это часы
         "-o", str(cache / "video.%(ext)s"), url],
        stdout=progress, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise Fail(*classify(proc.stderr))
    found = sorted(cache.glob("video.*"))
    if not found:
        raise Fail("unknown", "yt-dlp отработал, но файла нет:\n" + tail(proc.stderr))
    return found[0]


def extract_audio(ffmpeg, video, wav):
    log("аудио 16 кГц моно…")
    proc = run([ffmpeg, "-y", "-loglevel", "error", "-i", str(video),
                "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)])
    if proc.returncode != 0:
        raise Fail("unknown", "ffmpeg не смог извлечь аудио:\n" + tail(proc.stderr))
    return wav


def pipeline(args):
    video_ref = parse_vk_url(args.url)
    key = f"{video_ref['owner_id']}_{video_ref['video_id']}"
    cache = CACHE_ROOT / key
    cache.mkdir(parents=True, exist_ok=True)
    meta_file = cache / "meta.json"

    cached = {}
    if meta_file.exists() and not args.force:
        try:
            cached = json.loads(meta_file.read_text("utf-8"))
        except ValueError:
            cached = {}

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise Fail("no_ffmpeg", FFMPEG_HINT)

    warnings = []
    if cached.get("title"):
        log("метаданные из кэша")
        info = {k: cached.get(k) for k in
                ("title", "uploader", "duration", "upload_date", "description")}
    else:
        info = fetch_meta(video_ref["canonical"], args.cookies_from_browser)

    # кэш 480p не годится, если в этот раз просят 720p
    stale = args.force or cached.get("max_height", args.max_height) < args.max_height
    if stale:
        for old in cache.glob("video.*"):
            old.unlink()  # иначе yt-dlp увидит файл и не станет ничего качать
    existing = [] if stale else sorted(cache.glob("video.*"))
    video = existing[0] if existing else download(
        video_ref["canonical"], args.cookies_from_browser, args.max_height, cache)

    wav = cache / "audio.wav"
    if args.force or not wav.exists():
        extract_audio(ffmpeg, video, wav)

    transcript_json, transcript_txt = cache / "transcript.json", cache / "transcript.txt"
    if args.no_transcribe:
        warnings.append("транскрипт отключён флагом --no-transcribe")
    elif args.force or not transcript_json.exists():
        try:
            import transcribe
            transcribe.run(wav, transcript_json, transcript_txt, args.whisper_model, log)
        except ImportError:
            warnings.append(WHISPER_HINT)
            log("! " + WHISPER_HINT)
        except Exception as exc:  # модель не скачалась, мало памяти и т.п.
            warnings.append(f"транскрипт не получился: {exc}")
            log(f"! транскрипт не получился: {exc}")

    reuse = (cached.get("frames") and not args.force and existing
             and len(cached["frames"]) <= args.max_frames
             and all(Path(f["path"]).exists() for f in cached["frames"]))
    if reuse:
        log("кадры из кэша")
        shots = cached["frames"]
    else:
        shutil.rmtree(cache / "frames", ignore_errors=True)
        shots = frames.extract(ffmpeg, video, cache / "frames",
                               info["duration"], args.max_frames, log)

    result = {
        "ok": True,
        "id": key,
        "url": video_ref["canonical"],
        "kind": video_ref["kind"],
        **info,
        "cache_dir": str(cache),
        "max_height": args.max_height,
        "video_path": str(video),
        "audio_path": str(wav),
        "transcript_path": str(transcript_json) if transcript_json.exists() else None,
        "transcript_txt": str(transcript_txt) if transcript_txt.exists() else None,
        "frames": shots,
        "warnings": warnings,
    }
    meta_file.write_text(json.dumps(result, ensure_ascii=False, indent=1), "utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Скачать видео из ВК и разобрать его на транскрипт и кадры")
    parser.add_argument("url", help="ссылка на vkvideo.ru или vk.com")
    parser.add_argument("--max-height", type=int, default=480,
                        help="потолок качества, по умолчанию 480")
    parser.add_argument("--cookies-from-browser",
                        help="chrome/firefox/edge/... — для закрытых и 18+ видео")
    parser.add_argument("--no-transcribe", action="store_true", help="не гонять whisper")
    parser.add_argument("--whisper-model", default="small", help="tiny/base/small/medium/large-v3")
    parser.add_argument("--max-frames", type=int, default=40,
                        help="жёсткий потолок кадров, по умолчанию 40")
    parser.add_argument("--force", action="store_true", help="игнорировать кэш")
    args = parser.parse_args()

    try:
        result = pipeline(args)
    except VkUrlError as exc:
        result = {"ok": False, "error_code": "bad_url", "message": str(exc)}
    except Fail as exc:
        result = {"ok": False, "error_code": exc.code, "message": exc.message}
    except KeyboardInterrupt:
        result = {"ok": False, "error_code": "interrupted", "message": "Прервано пользователем"}
    except Exception as exc:  # что угодно ещё: диск, права, сеть — но не стектрейс в лицо
        result = {"ok": False, "error_code": "unknown",
                  "message": f"Неожиданная ошибка: {type(exc).__name__}: {exc}"}

    print(json.dumps(result, ensure_ascii=False, indent=1))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
