"""Dependency-light helpers for real WAV ingestion, scoring, and cancellation."""
from __future__ import annotations

import math
import struct
import time
import unicodedata
import wave
from pathlib import Path
from dataclasses import dataclass
from threading import Event


def inspect_pcm_wav(path: str | Path) -> dict:
    """Validate the prototype's PCM contract and return measured audio facts."""
    try:
        with wave.open(str(path), "rb") as wav:
            channels, width, rate, frames = (
                wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()
            )
            raw = wav.readframes(frames)
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"unsupported or corrupted WAV: {path}") from exc
    if (channels, width, rate) != (1, 2, 16000) or frames <= 0:
        raise ValueError(
            f"expected mono 16-bit 16 kHz PCM WAV, got channels={channels}, "
            f"width={width}, rate={rate}, frames={frames}"
        )
    samples = struct.unpack(f"<{frames}h", raw)
    rms = math.sqrt(sum(sample * sample for sample in samples) / frames)
    return {
        "channels": channels, "sample_width": width, "sample_rate": rate,
        "frames": frames, "duration_s": frames / rate, "rms": rms,
        "speech_detected": rms >= 100.0,
    }


def normalized_words(text: str) -> list[str]:
    cleaned = "".join(
        ch.lower() if (ch.isalnum() or ch.isspace()) else " "
        for ch in unicodedata.normalize("NFKD", text)
        if unicodedata.category(ch) != "Mn"
    )
    return cleaned.split()


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref, hyp = normalized_words(reference), normalized_words(hypothesis)
    previous = list(range(len(hyp) + 1))
    for index, expected in enumerate(ref, 1):
        current = [index] + [0] * len(hyp)
        for j, observed in enumerate(hyp, 1):
            current[j] = min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + (expected != observed))
        previous = current
    return previous[-1] / max(1, len(ref))


def nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("values cannot be empty")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def stream_until_cancelled(path: str | Path, cancel: Event, chunk_ms: int = 10) -> dict:
    """Realtime software playback sink; never emits to user hardware."""
    with wave.open(str(path), "rb") as wav:
        frames_per_chunk = max(1, wav.getframerate() * chunk_ms // 1000)
        chunks = 0
        while wav.readframes(frames_per_chunk):
            if cancel.wait(chunk_ms / 1000):
                return {"cancelled": True, "chunks": chunks, "detected_at_ns": time.perf_counter_ns()}
            chunks += 1
    return {"cancelled": False, "chunks": chunks, "detected_at_ns": None}


@dataclass(frozen=True)
class VadResult:
    speech_detected: bool
    voiced_frames: int
    total_frames: int
    voiced_ratio: float
    latency_ms: float


def webrtc_vad_wav(path: str | Path, aggressiveness: int = 2, frame_ms: int = 30) -> VadResult:
    """Run the native WebRTC VAD over a mono 16-bit PCM WAV."""
    import webrtcvad

    started = time.perf_counter()
    info = inspect_pcm_wav(path)
    vad = webrtcvad.Vad(aggressiveness)
    with wave.open(str(path), "rb") as wav:
        pcm = wav.readframes(wav.getnframes())
    frame_bytes = int(info["sample_rate"] * frame_ms / 1000) * 2
    frames = [pcm[i:i + frame_bytes] for i in range(0, len(pcm) - frame_bytes + 1, frame_bytes)]
    voiced = sum(vad.is_speech(frame, int(info["sample_rate"])) for frame in frames)
    ratio = voiced / len(frames) if frames else 0.0
    return VadResult(voiced > 0 and ratio >= 0.05, voiced, len(frames), ratio, (time.perf_counter() - started) * 1000)


@dataclass(frozen=True)
class AdapterResult:
    ok: bool
    value: object | None = None
    error: str | None = None
    timed_out: bool = False
    fallback: str = "text_or_voice_note"


def execute_bounded_adapter(call, timeout_s: float) -> AdapterResult:
    """Execute an STT/TTS adapter behind a timeout and fail-closed result."""
    import queue
    import threading

    results = queue.Queue(maxsize=1)
    def target():
        try:
            results.put((True, call()))
        except Exception as exc:
            results.put((False, f"{type(exc).__name__}: {exc}"))
    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(timeout_s)
    if worker.is_alive():
        return AdapterResult(False, error=f"adapter timeout after {timeout_s}s", timed_out=True)
    ok, payload = results.get_nowait()
    return AdapterResult(True, value=payload) if ok else AdapterResult(False, error=payload)
