"""Транскрипт через faster-whisper: transcript.json (с таймкодами) + transcript.txt."""
import json


def run(audio, json_path, txt_path, model_name="small", log=print):
    """Бросает ImportError, если faster-whisper не установлен — это ловит вызывающий."""
    from faster_whisper import WhisperModel

    log(f"whisper: модель {model_name}, это надолго…")
    try:
        model = WhisperModel(model_name, device="cuda", compute_type="float16")
    except Exception:  # нет GPU/CUDA — обычный случай
        model = WhisperModel(model_name, device="cpu", compute_type="int8")

    segments, info = model.transcribe(str(audio), language="ru", vad_filter=True)
    segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in segments]

    json_path.write_text(
        json.dumps({"language": info.language, "duration": round(info.duration, 2),
                    "model": model_name, "segments": segs}, ensure_ascii=False, indent=1),
        "utf-8")
    txt_path.write_text("\n".join(s["text"] for s in segs), "utf-8")
    log(f"транскрипт: {len(segs)} сегментов")
    return segs


if __name__ == "__main__":  # python transcribe.py audio.wav [модель]
    import sys
    from pathlib import Path

    wav = Path(sys.argv[1])
    run(wav, wav.with_name("transcript.json"), wav.with_name("transcript.txt"),
        sys.argv[2] if len(sys.argv) > 2 else "small")
