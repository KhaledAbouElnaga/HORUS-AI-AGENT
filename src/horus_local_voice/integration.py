"""M4 audio-to-runtime orchestration with no implicit fake runtime.

The engine and runtime are dependency-injected so the replay/live paths use the
same coordinator. A missing real HORUS transport is surfaced as BLOCKED by the
caller rather than converted into a successful deterministic response.
"""
from __future__ import annotations

import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .runtime_adapter import RuntimeCancelled, VoiceRuntimeAdapter
from .streaming import IncrementalTranscriber, PipelinedResponder


@dataclass
class IntegrationMetrics:
    vad_to_final_stt_ms: float | None = None
    runtime_response_ready_ms: float | None = None
    final_to_first_token_ms: float | None = None  # native only; intentionally unset here
    first_token_to_first_audio_ms: float | None = None  # native only; intentionally unset here
    user_end_to_first_audio_ms: float | None = None
    memory_lookup_ms: list[float] = field(default_factory=list)
    tool_ms: list[float] = field(default_factory=list)
    cancelled: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IntegratedTurn:
    session_id: str
    transcript: str
    response: str
    audio_chunks: int
    metrics: IntegrationMetrics


class VoiceRuntimePipeline:
    """Connect WAV/live PCM, incremental STT, HORUS, and incremental TTS."""

    def __init__(
        self,
        adapter: VoiceRuntimeAdapter,
        transcriber: IncrementalTranscriber,
        synthesize: Callable[[str], object],
        emit_audio: Callable[[object], None],
    ):
        self.adapter = adapter
        self.transcriber = transcriber
        self.responder = PipelinedResponder(synthesize, emit_audio)

    @staticmethod
    def _read_pcm(path: str | Path) -> bytes:
        with wave.open(str(path), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth()) != (1, 2):
                raise ValueError("integration replay requires mono 16-bit PCM WAV")
            return wav.readframes(wav.getnframes())

    def run_wav_turn(self, session_id: str, path: str | Path) -> IntegratedTurn:
        started = time.perf_counter()
        partials = self.transcriber.run(self._read_pcm(path))
        if not partials or not partials[-1].text:
            raise ValueError("streaming STT produced no final transcript")
        transcript = partials[-1].text
        stt_done = time.perf_counter()
        tokens = self.adapter.stream_turn(session_id, transcript)
        runtime_ready_at: float | None = None
        observed: list[str] = []
        def measured_tokens():
            nonlocal runtime_ready_at
            for token in tokens:
                if runtime_ready_at is None:
                    runtime_ready_at = time.perf_counter()
                observed.append(token)
                yield token

        first_audio_at: float | None = None
        emitted = 0
        def measured_audio(audio):
            nonlocal first_audio_at, emitted
            if first_audio_at is None:
                first_audio_at = time.perf_counter()
            emitted += 1
            self._emit_audio(audio)
        self._emit_audio = self.responder.emit_audio
        self.responder.emit_audio = measured_audio
        try:
            result = self.responder.run(measured_tokens(), strategy="phrase")
        except RuntimeCancelled:
            metrics = IntegrationMetrics(cancelled=True, errors=["runtime cancellation rejected stale output"])
            raise RuntimeError(f"turn cancelled for {session_id}: {metrics.errors[0]}")
        finally:
            self.responder.emit_audio = self._emit_audio
        metrics = IntegrationMetrics(
            vad_to_final_stt_ms=(stt_done - started) * 1000,
            runtime_response_ready_ms=((runtime_ready_at - stt_done) * 1000 if runtime_ready_at else None),
            # This transport is synchronous; native first-token values stay None.
            final_to_first_token_ms=None,
            first_token_to_first_audio_ms=None,
            user_end_to_first_audio_ms=((first_audio_at - started) * 1000 if first_audio_at else None),
            cancelled=result.cancelled,
        )
        return IntegratedTurn(session_id, transcript, "".join(observed), emitted, metrics)

    def cancel(self, session_id: str) -> None:
        self.adapter.cancel(session_id)
        self.responder.cancel()
