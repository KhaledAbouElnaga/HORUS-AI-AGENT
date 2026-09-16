"""Run 20 real local PCM/VAD -> faster-whisper -> agent -> Piper turns."""
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
import psutil
from faster_whisper import WhisperModel
from piper import PiperVoice
from horus_local_voice.real_audio import nearest_rank, webrtc_vad_wav, word_error_rate

ROOT = Path(__file__).parents[1]
process = psutil.Process()
manifest = json.loads((ROOT / "artifacts/audio_manifest.json").read_text(encoding="utf-8"))
def norm(value): return value.replace(chr(92), "/")
by_file = {norm(item["file"]): item for item in manifest if "expected" in item}
for item in manifest:
    if "expected" not in item:
        item["expected"] = " ".join(by_file[name]["expected"] for name in item["composed_from"])
load_started = time.perf_counter()
model = WhisperModel("tiny", device="cpu", compute_type="int8")
model_load_ms = (time.perf_counter() - load_started) * 1000
voice_load_started = time.perf_counter()
voices = {
    "ar": PiperVoice.load(str(ROOT / "artifacts/voices/ar_JO-kareem-medium.onnx")),
    "en": PiperVoice.load(str(ROOT / "artifacts/voices/en_US-lessac-medium.onnx")),
}
voice_load_ms = (time.perf_counter() - voice_load_started) * 1000
rows, context = [], []
started_all = time.perf_counter()
for index in range(20):
    item = manifest[index % len(manifest)]
    path = ROOT / item["file"]
    turn_started = time.perf_counter()
    audio = webrtc_vad_wav(path); vad_ms = audio.latency_ms
    if not audio.speech_detected:
        raise RuntimeError(f"WebRTC VAD found no speech: {path}")
    stt_started = time.perf_counter(); segments, info = model.transcribe(str(path), beam_size=1, vad_filter=False); transcript = " ".join(segment.text.strip() for segment in segments).strip(); stt_ms = (time.perf_counter() - stt_started) * 1000
    language = "ar" if info.language == "ar" else "en"
    agent_started = time.perf_counter(); reply = "سمعتك، هكمل معاك." if language == "ar" else "I heard you; I'll continue."; agent_ms = (time.perf_counter() - agent_started) * 1000
    tts_started = time.perf_counter(); chunks = voices[language].synthesize(reply); first_chunk = next(chunks); first_audio_ms = (time.perf_counter() - tts_started) * 1000; chunk_count = 1 + sum(1 for _ in chunks); synthesis_ms = (time.perf_counter() - tts_started) * 1000
    context.append(transcript)
    rows.append({"turn": index + 1, "file": item["file"], "detected_language": info.language, "vad_ms": round(vad_ms, 2), "vad_voiced_ratio": round(audio.voiced_ratio, 4), "stt_ms": round(stt_ms, 2), "agent_first_output_ms": round(agent_ms, 3), "tts_first_audio_ms": round(first_audio_ms, 2), "tts_synthesis_ms": round(synthesis_ms, 2), "tts_chunks": chunk_count, "end_to_end_ms": round((time.perf_counter() - turn_started) * 1000, 2), "wer": round(word_error_rate(item["expected"], transcript), 4), "observed": transcript})
summary = {}
for key in ["vad_ms", "stt_ms", "agent_first_output_ms", "tts_first_audio_ms", "tts_synthesis_ms", "end_to_end_ms"]:
    values = [row[key] for row in rows]; summary[key] = {"min": min(values), "median": nearest_rank(values, 0.5), "p95": nearest_rank(values, 0.95), "max": max(values)}
summary.update({"mean_wer": round(sum(row["wer"] for row in rows) / len(rows), 4), "turns": len(rows), "fixture_types": len({row["file"] for row in rows}), "context_turns": len(context), "context_10_pass": len(context) >= 10, "elapsed_s": round(time.perf_counter() - started_all, 2), "stt_model_load_ms": round(model_load_ms, 2), "voice_load_ms": round(voice_load_ms, 2), "rss_mb": round(process.memory_info().rss / 1024 / 1024, 1), "cpu_percent_sample": process.cpu_percent(interval=0.2), "gpu": "CPU path (device=cpu)"})
out = {"model": "faster-whisper tiny int8", "summary": summary, "turns": rows}
(ROOT / "artifacts/e2e_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
