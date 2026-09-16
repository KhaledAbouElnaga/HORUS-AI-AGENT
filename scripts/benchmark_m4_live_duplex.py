"""Ten overlapping live duplex trials with measured post-cancel output."""
import audioop
import json
import statistics
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from piper import PiperVoice

from horus_local_voice.real_audio import nearest_rank

ART = Path("artifacts")
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
SCALE = 0.20

hostapis = sd.query_hostapis(); devices = sd.query_devices()
def pick(kind, fragment):
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    matches = [(i, d) for i, d in enumerate(devices)
               if d[key] > 0 and fragment.lower() in d["name"].lower()
               and "WASAPI" in hostapis[d["hostapi"]]["name"]]
    if not matches:
        raise RuntimeError(f"no WASAPI {kind} matching {fragment}")
    return matches[0]
input_device, input_info = pick("input", "Microphone (C-Media")
output_device, output_info = pick("output", "Speakers (C-Media")

voice = PiperVoice.load(str(ART / "voices/en_US-lessac-medium.onnx"))
raw = bytearray(); source_rate = None
for chunk in voice.synthesize("This active local response is being interrupted by the user."):
    source_rate = chunk.sample_rate; raw.extend(chunk.audio_int16_bytes)
converted = bytes(raw)
if source_rate != SAMPLE_RATE:
    converted, _ = audioop.ratecv(converted, 2, 1, source_rate, SAMPLE_RATE, None)
audio = (np.frombuffer(converted, dtype=np.int16).astype(np.float32) * SCALE).astype(np.int16)
if audio.size == 0 or not np.any(audio != 0):
    raise RuntimeError("Piper output is empty or silent")

rows = []
for trial in range(1, 11):
    cancelled = threading.Event(); ready = threading.Event()
    state = {"offset": 0, "input_callbacks": 0, "input_frames": 0, "active_nonzero": 0,
                 "post_cancel_nonzero": 0, "rms_peak": 0.0, "signal_ns": None, "silence_ns": None,
                 "last_block_nonzero": 0}

    def input_callback(indata, frames, time_info, status):
        state["input_callbacks"] += 1; state["input_frames"] += len(indata)
        state["rms_peak"] = max(state["rms_peak"], float(np.sqrt(np.mean(indata.astype(np.float32) ** 2))))
        if state["input_callbacks"] >= 10 and not cancelled.is_set():
            state["signal_ns"] = time.perf_counter_ns(); cancelled.set(); ready.set()

    def output_callback(outdata, frames, time_info, status):
        outdata.fill(0)
        if cancelled.is_set():
            if state["silence_ns"] is None:
                state["silence_ns"] = time.perf_counter_ns()
            state["post_cancel_nonzero"] += int(np.count_nonzero(outdata))
            return
        start = state["offset"]; end = min(start + frames, len(audio))
        if end > start:
            outdata[:end - start, 0] = audio[start:end]
        block_nonzero = int(np.count_nonzero(outdata))
        state["offset"] = end; state["active_nonzero"] += block_nonzero; state["last_block_nonzero"] = block_nonzero
        if end >= len(audio):
            raise RuntimeError("active output ended before interruption")

    input_stream = sd.InputStream(device=input_device, samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
                                  channels=1, dtype="int16", callback=input_callback)
    output_stream = sd.OutputStream(device=output_device, samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
                                    channels=1, dtype="int16", callback=output_callback)
    start_ns = time.perf_counter_ns(); output_stream.start(); input_stream.start()
    if not ready.wait(5):
        output_stream.abort(); input_stream.abort(); raise TimeoutError("no live input callbacks")
    time.sleep(0.03)
    output_stream.stop(); stop_ns = time.perf_counter_ns(); output_stream.close()
    input_stream.stop(); input_stream.close()
    if state["silence_ns"] is None:
        raise RuntimeError("output callback never emitted cancellation silence")
    row = {"trial": trial, "overlap_ms_before_interrupt": (state["signal_ns"] - start_ns) / 1e6,
               "callback_silence_latency_ms": (state["silence_ns"] - state["signal_ns"]) / 1e6,
               "physical_stream_stop_ms": (stop_ns - state["signal_ns"]) / 1e6,
               "active_output_nonzero_samples": state["active_nonzero"],
               "last_block_nonzero_at_signal": state["last_block_nonzero"],
               "post_cancel_nonzero_samples": state["post_cancel_nonzero"],
               "input_callbacks_while_output_active": state["input_callbacks"],
               "input_frames_discarded": state["input_frames"], "microphone_rms_peak": state["rms_peak"],
               "speech_start_source": "deterministic injected event while live microphone callback active",
               "raw_audio_retained": False}
    row["pass"] = row["active_output_nonzero_samples"] > 0 and row["last_block_nonzero_at_signal"] > 0 and row["post_cancel_nonzero_samples"] == 0
    rows.append(row); print("live-duplex", trial, row["physical_stream_stop_ms"], flush=True)

out = {"trials": len(rows), "passed": sum(x["pass"] for x in rows),
       "mode": "concurrent dynamically selected C-Media WASAPI input/output streams; active 20%-scale Piper speech",
       "input_device": input_info["name"], "output_device": output_info["name"], "sample_rate": SAMPLE_RATE,
       "true_overlap": all(x["input_callbacks_while_output_active"] >= 10 for x in rows),
       "active_nonzero_audio": all(x["active_output_nonzero_samples"] > 0 and x["last_block_nonzero_at_signal"] > 0 for x in rows),
       "live_input_callback": True,
       "callback_silence_p50_ms": statistics.median(x["callback_silence_latency_ms"] for x in rows),
       "callback_silence_p95_ms": nearest_rank([x["callback_silence_latency_ms"] for x in rows], .95),
       "physical_stop_p50_ms": statistics.median(x["physical_stream_stop_ms"] for x in rows),
       "physical_stop_p95_ms": nearest_rank([x["physical_stream_stop_ms"] for x in rows], .95),
       "stale_output_failures": sum(not x["pass"] for x in rows), "raw_audio_retained": False,
       "rows": rows}
(ART / "m4_live_duplex_overlap.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "rows"}))
