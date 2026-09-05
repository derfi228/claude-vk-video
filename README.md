# vk-video

Плагин для Claude Code: «разбери вот это видео из ВК» — и Клод отвечает по
содержанию. Скачивает ролик с `vkvideo.ru` / `vk.com`, достаёт звук, делает
транскрипт с таймкодами, нарезает кадры и работает уже с ними.

Никаких других плагинов и никакого VK API-токена не нужно.

```
Вы:   разбери https://vkvideo.ru/video-226836549_456240037,
      выпиши основные тезисы и покажи, что на слайдах

Клод: [python scripts/vk_fetch.py …]  скачиваю (<= 480p)… аудио 16 кГц моно…
      whisper: модель small… кадров: смена сцены 27, сетка 40

      <краткая суть в 2–3 предложениях>

      • 00:42 — тезис, подкреплённый таймкодом
      • 07:15 — что показали на слайде в этот момент
      • 21:03 — ответ на ваш вопрос, если он был
```

## Установка

```bash
/plugin install derfi228/vk-video
pip install -r requirements.txt
```

Плюс системный `ffmpeg` — pip его не ставит:

| ОС | Команда |
|---|---|
| Windows | `winget install Gyan.FFmpeg` (или `choco install ffmpeg`) |
| macOS | `brew install ffmpeg` |
| Linux | `sudo apt install ffmpeg` / `sudo dnf install ffmpeg` |

После установки откройте новый терминал, иначе `ffmpeg` не попадёт в PATH.

`faster-whisper` из `requirements.txt` можно и не ставить: без него плагин вернёт
видео и кадры, а в `warnings` напишет, что транскрипта не будет.

## Примеры запросов

- `разбери https://vkvideo.ru/video-226836549_456240037`
- `о чём этот ролик: <ссылка>`
- `сделай конспект с таймкодами: <ссылка>`
- `что показывают на слайдах в <ссылка>`
- `в этом видео говорят про цены? <ссылка>`

Скрипт можно дёргать и руками:

```bash
python scripts/vk_fetch.py "<URL>" --max-frames 20 --whisper-model medium
```

| Флаг | Зачем |
|---|---|
| `--max-height 720` | мелкий текст на слайдах; по умолчанию 480 |
| `--cookies-from-browser chrome` | закрытые сообщества, 18+, региональные блокировки |
| `--no-transcribe` | нужны только кадры |
| `--whisper-model tiny\|base\|small\|medium\|large-v3` | точность против времени |
| `--max-frames 40` | потолок кадров |
| `--force` | перекачать мимо кэша |

Кэш — в `~/.cache/vk-video/{owner}_{id}/`. Второй вопрос по тому же ролику ничего
не качает заново.

## Если не работает

1. **`Unable to extract` / `extractor_broken`** — ВК поменял отдачу видео.
   `pip install -U yt-dlp` чинит это почти всегда. Не помогло — баг ещё открыт,
   смотрите [issues yt-dlp](https://github.com/yt-dlp/yt-dlp/issues?q=is%3Aissue+vk).
2. **`auth_required`** — видео приватное, 18+ или закрыто в регионе. Добавьте
   `--cookies-from-browser chrome` (браузер при этом лучше закрыть).
3. **`no_ffmpeg`** — см. таблицу выше.

Подробности — в [troubleshooting.md](skills/watch-vk-video/references/troubleshooting.md).

## Ограничения

- Приватные видео, 18+ и закрытые сообщества — только через `--cookies-from-browser`.
- Прямые эфиры не поддерживаются, ссылки на канал и плейлист целиком — тоже.
- Качество транскрипта упирается в модель whisper: `small` путает имена и термины,
  `medium` и `large-v3` лучше и медленнее. На CPU транскрипт часового ролика — это
  десятки минут.
- ВК периодически ломает извлечение видео, и yt-dlp догоняет с задержкой в дни.
  Это не чинится на стороне плагина.
- Распознавание — русский язык (`language="ru"` в `scripts/transcribe.py`).

## Про закон и вежливость

Плагин скачивает видео во временный кэш на вашей машине, чтобы разобрать его
локально, и ничего никуда не загружает. Соблюдение правил ВК и авторских прав —
на вашей ответственности: не выкладывайте скачанное, не обходите ограничения
доступа и не используйте чужие ролики так, как автор не разрешал.

---

# vk-video (English)

Claude Code plugin: paste a VK Video link, ask about the content. It downloads
the clip from `vkvideo.ru` / `vk.com` via yt-dlp, extracts 16 kHz audio,
transcribes it with faster-whisper (timestamps included), samples frames
(scene-change + uniform grid), and hands Claude the paths.

Self-contained: no other plugins, no VK API token.

**Install:** `/plugin install derfi228/vk-video`, then `pip install -r requirements.txt`
and system `ffmpeg` (`brew install ffmpeg` / `winget install Gyan.FFmpeg` /
`sudo apt install ffmpeg`). `faster-whisper` is optional — without it you get
video and frames plus a warning instead of a crash.

**Usage:** just ask Claude — *"summarize https://vkvideo.ru/video-…"*, *"what's on
the slides?"*, *"does the speaker mention pricing?"*. Or run the script directly:
`python scripts/vk_fetch.py "<URL>" --max-frames 20`. Results are cached in
`~/.cache/vk-video/`, so follow-up questions cost nothing.

**Limits:** private / age-restricted / region-locked videos need
`--cookies-from-browser chrome`; live streams are not supported; transcript
quality depends on the whisper model; VK breaks the extractor now and then —
`pip install -U yt-dlp` is the fix. Downloads land in a local cache for analysis
only; respecting VK's terms and copyright is on you.

MIT.
