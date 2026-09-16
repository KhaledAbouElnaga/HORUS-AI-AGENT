"""Measure native WebRTC VAD on speech, silence, and low-level noise."""
import json
import random
import struct
import time
import wave
from importlib.metadata import version
from pathlib import Path

from horus_local_voice.real_audio import webrtc_vad_wav

OUT = Path("artifacts/vad")
OUT.mkdir(parents=True, exist_ok=True)
def write(path, samples):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes(struct.pack("<" + "h" * len(samples), *samples))
silence = OUT / "silence.wav"; noise = OUT / "low_noise.wav"
write(silence, [0] * 16000)
random.seed(7); write(noise, [random.randint(-8, 8) for _ in range(16000)])
files = list(Path("artifacts/audio").glob("*.wav")) + [silence, noise]
started = time.perf_counter(); import webrtcvad
load_ms = (time.perf_counter() - started) * 1000
rows = []
for path in files:
    result = webrtc_vad_wav(path)
    rows.append({"file": str(path), **result.__dict__})
out = {"implementation": "WebRTC VAD native extension", "version": version("webrtcvad-wheels"), "load_ms": round(load_ms, 3), "aggressiveness": 2, "frame_ms": 30, "results": rows}
Path("artifacts/vad_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out))
