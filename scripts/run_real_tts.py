"""Run local Piper TTS for Egyptian-style Arabic, MSA, and English."""
import json
import time
import wave
from pathlib import Path

import psutil
from piper import PiperVoice

ROOT = Path(__file__).parents[1]
OUT = ROOT / "artifacts/tts"
OUT.mkdir(parents=True, exist_ok=True)
CASES = [
    ("egyptian_arabic", "ar_JO-kareem-medium", "أهلاً يا هورس، عامل إيه النهارده؟", "https://huggingface.co/rhasspy/piper-voices/tree/main/ar/ar_JO/kareem/medium"),
    ("msa", "ar_JO-kareem-medium", "مرحباً يا هورس، كيف حالك اليوم؟", "https://huggingface.co/rhasspy/piper-voices/tree/main/ar/ar_JO/kareem/medium"),
    ("english", "en_US-lessac-medium", "Hello HORUS, how are you today?", "https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium"),
]
loaded = {}
rows = []
process = psutil.Process()
for label, voice_name, text, source in CASES:
    if voice_name not in loaded:
        load_started = time.perf_counter(); loaded[voice_name] = PiperVoice.load(str(ROOT / "artifacts/voices" / f"{voice_name}.onnx")); load_ms = (time.perf_counter() - load_started) * 1000
    else:
        load_ms = 0.0
    voice = loaded[voice_name]
    output = OUT / f"{label}.wav"
    synth_started = time.perf_counter(); chunks = voice.synthesize(text); first = next(chunks); first_audio_ms = (time.perf_counter() - synth_started) * 1000; audio = [first, *chunks]; synthesis_ms = (time.perf_counter() - synth_started) * 1000
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(first.sample_rate)
        for chunk in audio: wav.writeframes(chunk.audio_int16_bytes)
    with wave.open(str(output), "rb") as wav: duration = wav.getnframes() / wav.getframerate()
    rows.append({"case": label, "voice": voice_name, "text": text, "file": output.relative_to(ROOT).as_posix(), "model_bytes": (ROOT / "artifacts/voices" / f"{voice_name}.onnx").stat().st_size, "load_ms": round(load_ms, 2), "first_audio_ms": round(first_audio_ms, 2), "synthesis_ms": round(synthesis_ms, 2), "output_duration_s": round(duration, 3), "process_rss_mb": round(process.memory_info().rss / 1024 / 1024, 1), "source": source, "license_note": "See upstream model card/dataset URL before redistribution"})
(ROOT / "artifacts/tts_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"cases": len(rows), "output": "artifacts/tts_results.json", "results": rows}, ensure_ascii=False))
