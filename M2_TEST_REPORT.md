# Milestone 2 Test Report

**Run date:** 2026-09-16 UTC
**Command:** `PYTHONPATH=src python -m pytest -q`

## Result

`7 passed in 0.02s`

| Area | Result | Evidence |
|---|---|---|
| Scripted Arabic/English/mixed turns | PASS | `tests/test_harness.py::test_scripted_turn_produces_metrics_and_reply`, fixture coverage test |
| Barge-in cancellation and stale output | PASS | `test_barge_in_cancels_stale_tts_output` |
| Ten-turn/session continuity | PASS | `test_context_survives_ten_turns` |
| Duplicate/out-of-order idempotency | PASS | `test_duplicate_and_out_of_order_events_are_idempotent` |
| Failure fallback | PASS | `test_channel_failure_enters_fallback` |
| Tool safety/audit decision | PASS | `test_tool_calls_fail_closed_and_are_audited` |
| Observability metrics | PASS | scripted-turn and fallback assertions |
| Syntax/compile | PASS | `python -m compileall -q src tests` |
| Real STT/TTS/audio path | PASS | `scripts/run_real_pipeline.py`: 20 real WAV -> faster-whisper -> deterministic agent -> Piper turns |
| Real Arabic fixture recognition | PASS | 5 Arabic WAV clips transcribed; mean WER proxy recorded in `M2_BENCHMARK.md` |
| Real English recognition | PASS | 2 English WAV clips transcribed |
| Real microphone/audio device | NOT YET MEASURED | Deterministic event harness only |
| Meta/WhatsApp realtime path | BLOCKED | Deliberately outside this milestone |
| Secret scan and isolation | PASS | See PR checks/report |

Real component execution is PASS; Egyptian conversational dialect quality remains NOT YET MEASURED because the fixtures are read benchmark sentences.

## Real local evidence

`python scripts/run_real_pipeline.py` executed 20 turns over 7 downloaded PCM WAV clips. faster-whisper `tiny`/CPU/int8 transcribed all source clips; Piper generated playable Arabic and English WAV output. An initial long transcript-to-TTS attempt failed with ONNX Runtime `bad allocation`; bounded deterministic response text is the recorded recovery boundary.
