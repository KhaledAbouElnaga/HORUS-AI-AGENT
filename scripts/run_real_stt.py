"""Run offline faster-whisper against every downloaded WAV fixture."""
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from faster_whisper import WhisperModel
from horus_local_voice.real_audio import inspect_pcm_wav, word_error_rate

ROOT = Path(__file__).parents[1]
manifest = json.loads((ROOT / "artifacts/audio_manifest.json").read_text(encoding="utf-8"))
def norm(value): return value.replace(chr(92), "/")
by_file = {norm(item["file"]): item for item in manifest if "expected" in item}
for item in manifest:
    if "expected" not in item and "composed_from" in item:
        item["expected"] = " ".join(by_file[name]["expected"] for name in item["composed_from"])
load_start = time.perf_counter()
model = WhisperModel("tiny", device="cpu", compute_type="int8")
load_ms = (time.perf_counter() - load_start) * 1000
results = []
for item in manifest:
    path = ROOT / item["file"]
    audio = inspect_pcm_wav(path)
    start = time.perf_counter()
    segments, info = model.transcribe(str(path), beam_size=1, vad_filter=False)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    results.append({**item, "observed": text, "wer": round(word_error_rate(item["expected"], text), 4), "latency_ms": round((time.perf_counter() - start) * 1000, 2), "duration_s": info.duration, "detected_language": info.language, "vad_rms": round(audio["rms"], 2)})
output = {"model": "tiny", "device": "cpu", "compute_type": "int8", "load_ms": round(load_ms, 2), "results": results}
(ROOT / "artifacts/stt_results.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"model": "tiny", "load_ms": round(load_ms, 2), "clips": len(results), "mean_wer": round(sum(row["wer"] for row in results) / len(results), 4), "output": "artifacts/stt_results.json"}, ensure_ascii=False))
