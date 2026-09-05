"""Кадры из видео: смена сцены + равномерная сетка. Всё через ffmpeg."""
import re
import subprocess

# длинная сторона <= 768 px, без апскейла
SCALE = "scale='min(768,iw)':'min(768,ih)':force_original_aspect_ratio=decrease"


def _thin(items, limit):
    """Равномерно проредить список до limit штук."""
    if limit <= 0:
        return []
    if len(items) <= limit:
        return items
    stride = len(items) / limit
    return [items[int(i * stride)] for i in range(limit)]


def _pass(ffmpeg, video, vf, out_dir, prefix, log):
    """Один проход ffmpeg. showinfo даёт точный pts каждого сохранённого кадра."""
    pattern = out_dir / f"{prefix}_%04d.jpg"
    proc = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "info", "-i", str(video),
         "-vf", f"{vf},{SCALE},showinfo", "-vsync", "vfr", "-q:v", "3", str(pattern)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        log(f"! кадры ({prefix}) не получились: {proc.stderr.strip()[-300:]}")
        return []
    times = [float(t) for t in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]
    files = sorted(out_dir.glob(f"{prefix}_*.jpg"))
    return [{"path": str(f), "t": round(t, 2), "scene": prefix == "scene"}
            for f, t in zip(files, times)]


def extract(ffmpeg, video, out_dir, duration, max_frames=40, log=print):
    """-> [{"path": ..., "t": секунды, "scene": bool}], отсортировано по времени."""
    out_dir.mkdir(parents=True, exist_ok=True)
    scenes = _pass(ffmpeg, video, "select='gt(scene,0.3)'", out_dir, "scene", log)
    step = max(duration / max_frames, 1.0) if duration and duration > 0 else 0
    grid = _pass(ffmpeg, video, f"fps=1/{step:.3f}", out_dir, "grid", log) if step else []
    log(f"кадров: смена сцены {len(scenes)}, сетка {len(grid)}")

    # кадр сетки рядом со сменой сцены — это тот же самый кадр
    grid = [g for g in grid if all(abs(g["t"] - s["t"]) > step / 2 for s in scenes)]
    scenes = _thin(scenes, max_frames)  # смена сцены в приоритете
    grid = _thin(grid, max_frames - len(scenes))
    picked = sorted(scenes + grid, key=lambda f: f["t"])

    chosen = {f["path"] for f in picked}
    for leftover in out_dir.glob("*.jpg"):
        if str(leftover) not in chosen:
            leftover.unlink()
    return picked
