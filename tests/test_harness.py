import json
from pathlib import Path

from horus_local_voice.harness import VoiceHarness
from horus_local_voice.events import Event


def test_scripted_turn_produces_metrics_and_reply():
    result = VoiceHarness().run([Event('speech_final', 'hello')])
    assert result.replies == ['Acknowledged: hello']
    assert 'end_to_end_turn_ms' in result.metrics


def test_barge_in_cancels_stale_tts_output():
    result = VoiceHarness().run([
        Event('speech_final', 'first'),
        Event('tts_started', 'old reply'),
        Event('speech_start', ''),
        Event('speech_final', 'interrupt'),
    ])
    assert result.cancelled_tts == 1
    assert 'old reply' not in result.emitted_audio
    assert result.replies[-1] == 'Acknowledged: interrupt'


def test_context_survives_ten_turns():
    events = [Event('speech_final', f'turn-{i}') for i in range(10)]
    result = VoiceHarness().run(events)
    assert result.context_size == 10
    assert result.context_assertions == 10


def test_duplicate_and_out_of_order_events_are_idempotent():
    events = [Event('speech_final', 'one', event_id='2'), Event('speech_final', 'one', event_id='2'), Event('speech_final', 'zero', event_id='1')]
    result = VoiceHarness().run(events)
    assert result.replies == ['Acknowledged: one']
    assert result.duplicates == 1
    assert result.out_of_order == 1


def test_channel_failure_enters_fallback():
    result = VoiceHarness().run([Event('channel_failure', 'whatsapp')])
    assert result.fallback == 'text_or_voice_note'
    assert result.metrics['fallback_transition_ms'] >= 0


def test_tool_calls_fail_closed_and_are_audited():
    result = VoiceHarness().run([Event('speech_final', 'tool:delete_everything')])
    assert result.tool_decisions == ['DENY']
    assert result.secrets_in_logs is False


def test_fixture_set_covers_required_languages():
    fixture = json.loads(Path('tests/fixtures/turns.json').read_text(encoding='utf-8'))
    languages = {row['language'] for row in fixture}
    assert {'ar-EG', 'ar', 'en', 'ar/en'} <= languages
    assert any(row['case'] == 'interruption' for row in fixture)
