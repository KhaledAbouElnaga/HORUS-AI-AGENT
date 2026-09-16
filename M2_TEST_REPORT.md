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
| Real Arabic STT/TTS quality | NOT YET MEASURED | No model download or external account was used |
| Real microphone/audio device | NOT YET MEASURED | Deterministic event harness only |
| Meta/WhatsApp realtime path | BLOCKED | Deliberately outside this milestone |
| Secret scan and isolation | PASS | See PR checks/report |

No PASS is claimed for real speech recognition, synthesis, or dialect quality.
