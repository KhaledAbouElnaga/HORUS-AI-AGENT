"""Dependency-light helpers for real WAV ingestion, scoring, and cancellation."""
from __future__ import annotations

import math
import struct
import time
import unicodedata
import wave
from pathlib import Path
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
