from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from threading import Event, Lock
from typing import Callable
from collections import deque


@dataclass(frozen=True)
class PartialResult:
    audio_ms: float
    text: str
    latency_ms: float
    stable: bool
    revisions: int


class IncrementalTranscriber:
    """Chunk-fed transcription boundary that exposes partial and final results."""
    def __init__(self, transcribe: Callable[[bytes], str], sample_rate: int = 16000, sample_width: int = 2):
        self.transcribe = transcribe
        self.bytes_per_ms = sample_rate * sample_width / 1000

    def run(self, pcm: bytes, chunk_ms: int = 800, min_partial_ms: int = 400) -> list[PartialResult]:
        rows, previous, revisions = [], "", 0
        step = max(1, int(chunk_ms * self.bytes_per_ms))
        for end in range(step, len(pcm) + step, step):
            prefix = pcm[:min(end, len(pcm))]
            if len(prefix) < int(min_partial_ms * self.bytes_per_ms):
                continue
            started = time.perf_counter()
            text = self.transcribe(prefix).strip()
            latency = (time.perf_counter() - started) * 1000
            if previous and not (text.startswith(previous) or previous.startswith(text)):
                revisions += 1
            previous = text
            rows.append(PartialResult(len(prefix) / self.bytes_per_ms, text, latency, len(prefix) >= len(pcm), revisions))
            if len(prefix) >= len(pcm):
                break
        return rows


@dataclass(frozen=True)
class EndpointPolicy:
    name: str
    start_voiced_frames: int
    end_unvoiced_frames: int
    max_utterance_frames: int = 200


@dataclass(frozen=True)
class EndpointResult:
    start_frame: int | None
    end_frame: int | None
    false_cut: bool
    tail_frames: int


def detect_endpoint(voiced: list[bool], policy: EndpointPolicy) -> EndpointResult:
    start = last_voiced = None
    run = silence = 0
    for index, is_voiced in enumerate(voiced):
        if is_voiced:
            run += 1; silence = 0; last_voiced = index
            if start is None and run >= policy.start_voiced_frames:
                start = index - run + 1
        else:
            run = 0
            if start is not None:
                silence += 1
                if silence >= policy.end_unvoiced_frames:
                    end = index + 1
                    return EndpointResult(start, end, any(voiced[end:]), end - (last_voiced if last_voiced is not None else end) - 1)
        if start is not None and index - start + 1 >= policy.max_utterance_frames:
            return EndpointResult(start, index + 1, any(voiced[index + 1:]), silence)
    return EndpointResult(start, len(voiced) if start is not None else None, False, silence)


def chunk_text(text: str, strategy: str, max_chars: int = 80) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    if strategy == "sentence":
        parts = [p.strip() for p in re.split(r"(?<=[.!?؟])\s+", text) if p.strip()]
    elif strategy == "phrase":
        parts = [p.strip() + ("," if not p.strip().endswith((".", "!", "?", "؟")) else "") for p in text.split(",") if p.strip()]
    else:
        raise ValueError("strategy must be sentence or phrase")
    out = []
    for part in parts:
        while len(part) > max_chars:
            cut = part.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            out.append(part[:cut].strip()); part = part[cut:].strip()
        if part:
            out.append(part)
    return out


def script_route(text: str) -> str:
    arabic = len(re.findall(r"[؀-ۿ]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return "en" if latin > arabic else "ar"


class CancellationEpoch:
    """Thread-safe epoch preventing stale generated text or audio from emission."""
    def __init__(self):
        self._lock = Lock(); self._epoch = 0; self._cancel = Event()

    def begin(self) -> tuple[int, Event]:
        with self._lock:
            self._epoch += 1; self._cancel = Event()
            return self._epoch, self._cancel

    def cancel(self) -> int:
        with self._lock:
            self._cancel.set(); self._epoch += 1
            return self._epoch

    def is_current(self, epoch: int) -> bool:
        with self._lock:
            return epoch == self._epoch and not self._cancel.is_set()


@dataclass
class StreamState:
    last_sequence: int = -1
    seen: set[str] = field(default_factory=set)
    stale: int = 0
    duplicates: int = 0

    def accept(self, event_id: str, sequence: int) -> bool:
        if event_id in self.seen:
            self.duplicates += 1; return False
        self.seen.add(event_id)
        if sequence <= self.last_sequence:
            self.stale += 1; return False
        self.last_sequence = sequence
        return True


@dataclass(frozen=True)
class AudioChunk:
    sequence: int
    captured_ns: int
    pcm: bytes
    sample_rate: int = 16000

    @property
    def captured_at_ns(self):
        return self.captured_ns


class BoundedAudioIngress:
    """Bounded chunk queue with explicit backpressure and shutdown semantics."""
    def __init__(self, max_chunks: int = 8):
        if max_chunks < 1: raise ValueError("max_chunks must be positive")
        self.max_chunks = max_chunks; self._chunks: list[AudioChunk] = []; self.state = "IDLE"; self.dropped = 0; self.high_water = 0

    def start(self) -> None:
        if self.state not in ("IDLE", "STOPPED"): raise RuntimeError("session already active")
        self.state = "LISTENING"

    def push(self, chunk: AudioChunk) -> bool:
        if self.state != "LISTENING": return False
        if len(self._chunks) >= self.max_chunks:
            self.dropped += 1; return False
        self._chunks.append(chunk); self.high_water = max(self.high_water, len(self._chunks)); return True

    def pop(self) -> AudioChunk | None:
        return self._chunks.pop(0) if self._chunks else None

    def shutdown(self) -> None:
        self._chunks.clear(); self.state = "STOPPED"

    close = shutdown

    def __len__(self) -> int:
        return self.depth

    @property
    def depth(self) -> int:
        return len(self._chunks)


@dataclass(frozen=True)
class PipelineResult:
    text: str
    text_chunks: int
    audio_chunks: int
    cancelled: bool


class PipelinedResponder:
    """Streams model deltas into bounded TTS phrases and a cancellable audio sink."""
    def __init__(self, synthesize: Callable[[str], object], emit_audio: Callable[[object], None], max_chars: int = 60):
        self.synthesize = synthesize
        self.emit_audio = emit_audio
        self.max_chars = max_chars
        self.epochs = CancellationEpoch()

    def cancel(self) -> None:
        self.epochs.cancel()

    def run(self, tokens, strategy: str = "phrase") -> PipelineResult:
        epoch, signal = self.epochs.begin()
        text = buffer = ""; text_chunks = audio_chunks = 0
        for token in tokens:
            if signal.is_set() or not self.epochs.is_current(epoch):
                return PipelineResult(text, text_chunks, audio_chunks, True)
            text += token; buffer += token
            ready = any(mark in buffer for mark in ".!?؟") or len(buffer) >= self.max_chars
            if ready:
                pieces = chunk_text(buffer, strategy, self.max_chars); buffer = ""
                for piece in pieces:
                    audio = self.synthesize(piece); text_chunks += 1
                    if signal.is_set() or not self.epochs.is_current(epoch):
                        return PipelineResult(text, text_chunks, audio_chunks, True)
                    self.emit_audio(audio); audio_chunks += 1
        if buffer.strip() and self.epochs.is_current(epoch):
            audio = self.synthesize(buffer.strip()); text_chunks += 1
            if self.epochs.is_current(epoch): self.emit_audio(audio); audio_chunks += 1
        return PipelineResult(text, text_chunks, audio_chunks, not self.epochs.is_current(epoch))




class WavChunkIngress:
    """Deterministic fixed-frame replay; chunks are never retained by the ingress."""
    def __init__(self, path: str, frame_ms: int = 30):
        self.path, self.frame_ms = path, frame_ms

    def __iter__(self):
        import wave
        with wave.open(self.path, "rb") as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                raise ValueError("mono int16 PCM required")
            count = wav.getframerate() * self.frame_ms // 1000
            sequence = 0
            while True:
                pcm = wav.readframes(count)
                if not pcm:
                    break
                yield AudioChunk(sequence, time.perf_counter_ns(), pcm, wav.getframerate())
                sequence += 1


class MicrophoneIngress:
    """Short live fixed-frame captures with no file retention."""
    def __init__(self, sample_rate: int = 16000, frame_ms: int = 30):
        self.sample_rate, self.frame_ms = sample_rate, frame_ms

    def capture(self, frames: int):
        import sounddevice as sd
        count = self.sample_rate * self.frame_ms // 1000
        for sequence in range(frames):
            pcm = sd.rec(count, samplerate=self.sample_rate, channels=1, dtype="int16", blocking=True)
            yield AudioChunk(sequence, time.perf_counter_ns(), pcm.tobytes(), self.sample_rate)
            del pcm


BoundedFrameQueue = BoundedAudioIngress


class StreamSession:
    def __init__(self, session_id: str, queue_size: int = 8):
        self.session_id = session_id
        self.state = "created"
        self.queue = BoundedFrameQueue(queue_size)
        self.restarts = 0
        self.metrics: list[dict] = []

    def start(self):
        if self.state not in {"created", "stopped"}:
            raise RuntimeError("invalid session transition")
        self.state = "listening"

    def recover(self, component: str):
        self.restarts += 1
        self.state = "listening"
        self.metrics.append({"event": "recovery", "component": component, "at_ns": time.perf_counter_ns()})

    def stop(self):
        self.state = "stopped"
        self.queue.close()
