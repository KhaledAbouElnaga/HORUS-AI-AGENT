"""Measure cancellation of a realtime software sink over a real Piper WAV."""
import json
import threading
import time
from pathlib import Path

from horus_local_voice.real_audio import nearest_rank, stream_until_cancelled

ROOT = Path(__file__).parents[1]
audio = ROOT / "artifacts/tts/english.wav"
rows = []
for _ in range(10):
    cancel = threading.Event()
    signal_ns = []
    def signal():
        signal_ns.append(time.perf_counter_ns()); cancel.set()
    timer = threading.Timer(0.050, signal)
    timer.start()
    result = stream_until_cancelled(audio, cancel, chunk_ms=5)
    timer.join()
    stopped_ns = result["detected_at_ns"]
    rows.append(round((stopped_ns - signal_ns[0]) / 1e6, 3))
result = {
    "runs": len(rows), "latencies_ms": rows, "min_ms": min(rows),
    "median_ms": nearest_rank(rows, 0.5), "p95_ms": nearest_rank(rows, 0.95),
    "all_cancelled": len(rows) == 10, "audio_file": "artifacts/tts/english.wav",
    "note": "realtime software sink over real Piper WAV; no user hardware output",
}
(ROOT / "artifacts/barge_in_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
