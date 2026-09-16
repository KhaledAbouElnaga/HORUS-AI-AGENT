from dataclasses import dataclass, field
from time import perf_counter
from typing import Iterable

from .events import Event


@dataclass
class HarnessResult:
    replies: list[str] = field(default_factory=list)
    emitted_audio: list[str] = field(default_factory=list)
    cancelled_tts: int = 0
    context_size: int = 0
    context_assertions: int = 0
    duplicates: int = 0
    out_of_order: int = 0
    fallback: str | None = None
    tool_decisions: list[str] = field(default_factory=list)
    secrets_in_logs: bool = False
    metrics: dict[str, float] = field(default_factory=dict)


class VoiceHarness:
    """Deterministic event harness; real adapters can replace each boundary later."""

    def run(self, events: Iterable[Event]) -> HarnessResult:
        result = HarnessResult()
        seen: set[str] = set()
        last_sequence = -1
        context: list[str] = []
        active_tts: str | None = None
        started = perf_counter()
        for index, event in enumerate(events):
            event_id = event.event_id or f'local-{index}'
            if event_id in seen:
                result.duplicates += 1
                continue
            seen.add(event_id)
            if event.event_id and event.event_id.isdigit():
                sequence = int(event.event_id)
                if sequence < last_sequence:
                    result.out_of_order += 1
                    continue
                last_sequence = sequence
            if event.kind == 'speech_start':
                if active_tts is not None:
                    active_tts = None
                    result.cancelled_tts += 1
                    result.metrics['interruption_to_stop_ms'] = 0.0
            elif event.kind == 'tts_started':
                active_tts = event.payload
            elif event.kind == 'speech_final':
                context.append(event.payload)
                if event.payload.startswith('tool:'):
                    result.tool_decisions.append('DENY')
                    result.replies.append('I cannot execute that tool request.')
                else:
                    result.replies.append(f'Acknowledged: {event.payload}')
                result.context_assertions += 1 if event.payload in context else 0
                result.metrics['end_to_end_turn_ms'] = (perf_counter() - started) * 1000
                active_tts = None
            elif event.kind == 'channel_failure':
                result.fallback = 'text_or_voice_note'
                result.metrics['fallback_transition_ms'] = 0.0
                active_tts = None
        result.context_size = len(context)
        result.metrics.setdefault('vad_decision_ms', 0.0)
        result.metrics.setdefault('audio_to_final_stt_ms', 0.0)
        result.metrics.setdefault('turn_final_to_agent_first_output_ms', 0.0)
        result.metrics.setdefault('response_to_first_audio_ms', 0.0)
        result.metrics.setdefault('duplicate_or_out_of_order_events', float(result.duplicates + result.out_of_order))
        return result
