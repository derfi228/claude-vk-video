# vk-video

Клод не умеет смотреть видео из ВК. Плагин это чинит: кидаете ссылку и спрашиваете,
о чём там, — он качает ролик, вытаскивает звук, прогоняет через whisper и нарезает
кадры. Дальше Клод читает транскрипт с таймкодами и смотрит картинки, а не
пересказывает заголовок.

Токен VK API не нужен, другие плагины тоже. Работают `vkvideo.ru`, `vk.com` и
`vk.ru` — страница видео, клип, embed, ссылка из плейлиста или со стены.

```
Вы:   разбери https://vkvideo.ru/video-17733403_456239836,
      выпиши тезисы с таймкодами

Клод: скачиваю (<= 480p)… аудио 16 кГц моно… whisper: модель small…
      транскрипт: 237 сегментов … кадров: смена сцены 50, сетка 40

      Десять минут про то, как устроена нейросеть, на школьной аналогии.

      • 00:10 — школьник подгоняет ответ контрольной под верный, а потом
                правит и предыдущее уравнение; отсюда и растёт обучение сети
      • 02:50 — рекламная врезка про мобильную игру
      • 04:40 — входной, скрытый и выходной слои: на выходе 10 нейронов,
                по одному на цифру
```

Это настоящий вывод, а не набросок: ролик Droider на 9:59 прошёл весь путь за
4 минуты — скачивание, звук, whisper `small` на голом CPU, кадры.

## Установка

В Клоде (или тем же `claude plugin ...` из терминала):

```bash
/plugin marketplace add derfi228/claude-vk-video
/plugin install vk-video@claude-vk-video
```

Дальше — зависимости, их Клод за вас не поставит:

```bash
pip install -r requirements.txt
```

Отдельно нужен `ffmpeg` — pip его не ставит:

| ОС | Команда |
|---|---|
| Windows | `winget install Gyan.FFmpeg` (или `choco install ffmpeg`) |
| macOS | `brew install ffmpeg` |
| Linux | `sudo apt install ffmpeg` / `sudo dnf install ffmpeg` |

После установки нужен новый терминал, иначе `ffmpeg` не окажется в PATH и плагин
скажет, что его нет.

`faster-whisper` в `requirements.txt` можно пропустить. Тогда вместо падения плагин
вернёт видео с кадрами и припиской в `warnings`, что транскрипта не будет: по
слайдам многое понятно и без звука.

## Как спрашивать

- `разбери <ссылка>`
- `о чём этот ролик: <ссылка>`
- `сделай конспект с таймкодами: <ссылка>`
- `что показывают на слайдах в <ссылка>`
- `тут говорят про цены? <ссылка>`

Скрипт живёт своей жизнью и запускается руками:

```bash
python scripts/vk_fetch.py "<URL>" --max-frames 20 --whisper-model medium
```

В stdout уходит только JSON с путями до видео, звука, транскрипта и кадров;
прогресс и ругань — в stderr.

| Флаг | Зачем |
|---|---|
| `--max-height 720` | текст на слайдах совсем мелкий; по умолчанию 480 |
| `--cookies-from-browser chrome` | закрытые сообщества, 18+, региональные блокировки |
| `--no-transcribe` | нужны только кадры |
| `--whisper-model tiny\|base\|small\|medium\|large-v3` | точность против времени |
| `--max-frames 40` | потолок кадров |
| `--force` | перекачать мимо кэша |

## Что происходит внутри

Качаем не выше 480p. Не из экономии ради экономии: в 480p текст на слайдах
читается (кадр выходит 768 px по длинной стороне), а 33-минутный ролик — это
всё равно четверть гигабайта. ВК отдаёт длинные видео фрагментами HLS, и в один
поток та самая четверть гигабайта ехала 12 минут; с `-N 4` — минуту.

Кадры собираются из двух источников: детектор смены сцены ловит слайды и склейки,
равномерная сетка страхует на случай, когда сцена не меняется полчаса. Дальше всё
это прореживается до 40 штук, кадры смены сцены переживают прореживание первыми.
Потолок жёсткий и обсуждению не подлежит: полсотни картинок забивают контекст, и
думать Клоду уже нечем.

Всё скачанное лежит в `~/.cache/vk-video/{owner}_{id}/`. Второй вопрос по тому же
ролику отвечается за доли секунды, потому что качать уже нечего. `--force` кэш
игнорирует.

Мелочь, которая ломалась: в ffmpeg 9 выкинули `-vsync`, а в сборках до 5.1 ещё нет
`-fps_mode`. Скрипт пробует сначала новый флаг, потом старый, вместо того чтобы
гадать по строке версии.

## Когда не работает

`extractor_broken` — ВК опять поменял отдачу видео. Почти всегда лечится
`pip install -U yt-dlp`; если нет, баг ещё открыт, смотрите
[issues yt-dlp](https://github.com/yt-dlp/yt-dlp/issues?q=is%3Aissue+vk).

`auth_required` — ролик приватный, 18+ или закрыт в вашей стране. Единственный
рабочий путь — куки браузера, где вы залогинены: `--cookies-from-browser chrome`.
Браузер при этом лучше закрыть, иначе он держит базу кук занятой.

`no_ffmpeg` — см. таблицу с командами выше.

Остальные коды и что с ними делать — в
[troubleshooting.md](skills/watch-vk-video/references/troubleshooting.md), этот же
файл Клод читает сам, когда пайплайн падает.

## Чего он не умеет

- Прямые эфиры. Ссылка на канал или на плейлист целиком — тоже мимо, нужен
  конкретный ролик.
- Приватное без кук. Если у вас нет доступа к видео в браузере, его не будет и здесь.
- Точный транскрипт на модели `small`: имена и термины она путает. Если в конспекте
  важны фамилии и цифры — ставьте `medium`, она заметно медленнее и заметно лучше.
- Русский по умолчанию: `language="ru"` прибит в `scripts/transcribe.py`.
- Пережить очередной ремонт ВК. yt-dlp догоняет за дни, и это не чинится на нашей
  стороне.

## Про закон

Плагин скачивает видео во временный кэш на вашей машине, разбирает его локально и
никуда ничего не отправляет. Правила ВК и авторские права — на вас: не
перевыкладывайте скачанное, не обходите ограничения доступа и не используйте чужие
ролики так, как автор не разрешал.

---

# vk-video (English)

Claude can't watch VK videos. This plugin fixes that: give it a link, ask what the
video is about, and it downloads the clip, pulls 16 kHz audio, transcribes it with
faster-whisper (timestamps included) and samples frames — scene changes plus a
uniform grid, capped at 40. Claude then reads the transcript and looks at the
frames instead of guessing from the title.

No VK API token, no other plugins. `vkvideo.ru`, `vk.com` and `vk.ru` links all
work: video pages, clips, embeds, playlist and wall links.

**Install:** `/plugin marketplace add derfi228/claude-vk-video`, then
`/plugin install vk-video@claude-vk-video`. After that
`pip install -r requirements.txt` and system `ffmpeg`
(`brew install ffmpeg` / `winget install Gyan.FFmpeg` / `sudo apt install ffmpeg`).
`faster-whisper` is optional — skip it and you still get video and frames, plus a
warning instead of a crash.

**Use it:** ask Claude — *"summarize https://vkvideo.ru/video-…"*, *"what's on the
slides?"*, *"do they mention pricing?"*. Or run the script yourself:
`python scripts/vk_fetch.py "<URL>" --max-frames 20`. It prints JSON to stdout and
nothing else; progress goes to stderr. Everything lands in `~/.cache/vk-video/`, so
the second question about the same video costs nothing.

**Caveats:** private, 18+ and geo-blocked videos need
`--cookies-from-browser chrome`; live streams aren't supported; `small` whisper
mangles names, use `medium` when they matter; VK breaks the extractor every few
months and `pip install -U yt-dlp` is the fix. Downloads stay in a local cache for
analysis — respecting VK's terms and copyright is on you.

MIT.
