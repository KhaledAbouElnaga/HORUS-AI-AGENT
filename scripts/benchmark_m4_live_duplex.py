import json
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

from horus_local_voice.real_audio import nearest_rank

ART = Path("artifacts")
PCM = ART / "m4_duplex_tts_44k.pcm"
child = """from pathlib import Path
from piper import PiperVoice
import audioop
art=Path(\"artifacts\")
voice=PiperVoice.load(str(art/\"voices/en_US-lessac-medium.onnx\"))
raw=b\"\"; rate=0
for chunk in voice.synthesize(\"This active local response is being interrupted by the user.\"):
 rate=chunk.sample_rate; raw+=chunk.audio_int16_bytes
if rate != 44100: raw,_=audioop.ratecv(raw,2,1,rate,44100,None)
(art/\"m4_duplex_tts_44k.pcm\").write_bytes(raw)
"""
subprocess.run([sys.executable, "-c", child], check=True)
audio = np.frombuffer(PCM.read_bytes(), dtype=np.int16)
audio = (audio.astype(np.float32) * 0.20).astype(np.int16)
rows = []
for trial in range(1, 11):
    cancelled = threading.Event(); ready = threading.Event()
    state = {"offset": 0, "input_callbacks": 0, "active_nonzero": 0, "post_cancel_nonzero": 0, "rms_peak": 0.0, "signal_ns": None, "silence_ns": None}
    def callback(indata, outdata, frames, time_info, status):
        state["input_callbacks"] += 1
        state["rms_peak"] = max(state["rms_peak"], float(np.sqrt(np.mean(indata.astype(np.float32) ** 2))))
        if state["input_callbacks"] >= 10 and not cancelled.is_set():
            state["signal_ns"] = time.perf_counter_ns(); cancelled.set(); ready.set()
        outdata.fill(0)
        if cancelled.is_set():
            state["silence_ns"] = state["silence_ns"] or time.perf_counter_ns()
            state["post_cancel_nonzero"] += int(np.count_nonzero(outdata))
            return
        start = state["offset"]; end = min(start + frames, len(audio))
        if end > start: outdata[:end-start, 0] = audio[start:end]
        state["offset"] = end; state["active_nonzero"] += int(np.count_nonzero(outdata))
    stream = sd.Stream(device=(1, 5), samplerate=44100, blocksize=1024, channels=1, dtype="int16", callback=callback)
    start_ns = time.perf_counter_ns(); stream.start()
    if not ready.wait(5): stream.abort(); stream.close(); raise TimeoutError("no live input callbacks")
    time.sleep(0.03)
    stream.stop(); stop_ns = time.perf_counter_ns(); stream.close()
    row = {"trial": trial, "overlap_ms_before_interrupt": (state["signal_ns"] - start_ns) / 1e6, "callback_silence_latency_ms": (state["silence_ns"] - state["signal_ns"]) / 1e6, "physical_stream_stop_ms": (stop_ns - state["signal_ns"]) / 1e6, "active_output_nonzero_samples": state["active_nonzero"], "post_cancel_nonzero_samples": state["post_cancel_nonzero"], "input_callbacks_while_output_active": state["input_callbacks"], "microphone_rms_peak": state["rms_peak"], "speech_start_source": "deterministic injected event while live microphone callback active", "raw_audio_retained": False}
    row["pass"] = row["active_output_nonzero_samples"] > 0 and row["post_cancel_nonzero_samples"] == 0
    rows.append(row); print("live-duplex", trial, row["physical_stream_stop_ms"], flush=True)
out = {"trials": 10, "passed": sum(x["pass"] for x in rows), "true_overlap": all(x["input_callbacks_while_output_active"] >= 10 for x in rows), "active_nonzero_audio": all(x["active_output_nonzero_samples"] > 0 for x in rows), "live_input_callback": True, "callback_silence_p50_ms": statistics.median(x["callback_silence_latency_ms"] for x in rows), "callback_silence_p95_ms": nearest_rank([x["callback_silence_latency_ms"] for x in rows], .95), "physical_stop_p50_ms": statistics.median(x["physical_stream_stop_ms"] for x in rows), "physical_stop_p95_ms": nearest_rank([x["physical_stream_stop_ms"] for x in rows], .95), "stale_output_failures": sum(not x["pass"] for x in rows), "rows": rows}
(ART / "m4_live_duplex_overlap.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "rows"}))
