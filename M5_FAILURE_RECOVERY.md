# M5 Failure and Recovery Report

## Active M5 failure matrix

Command: `PYTHONPATH=src python scripts/run_m5_failure_matrix.py`

| Injection | State | Recovery / stale output |
|---|---|---|
| runtime unavailable/exception | PASS | fails closed with `RuntimeUnavailable` / `RuntimeError`; stale 0 |
| memory read failure | PASS | exception propagates; real retry path; stale 0 |
| memory write/update failure | PASS | exception propagates; no fabricated write; stale 0 |
| tool timeout | PASS | exception propagates; real retry path; stale 0 |
| tool exception | PASS | exception propagates; stale 0 |
| malformed tool result | PASS | adapter rejects `object`; stale 0 |
| cancellation during/after tool result | PASS / PARTIAL | `RuntimeCancelled`; no downstream output; native mid-stream timing unavailable |
| TTS failure | PASS | failed emission discarded and real response retry succeeds; stale 0 |
| session restart/reconnect | PASS | `resume_session()` clears cancellation and real `/status` succeeds |
| queue overload/backpressure | PASS | bounded ingress drops newest chunk explicitly; no stale output |

## Three real recovery events in the integrated local path

Artifact: `artifacts/m5_recovery_events.json`, command: `PYTHONPATH=src python scripts/run_m5_recovery_events.py`.

| Turn | Injected failure | Component | Recovery behavior | Stale output |
|---:|---|---|---|---:|
| 12 | memory read failure | memory | restore real port and retry succeeded | 0 |
| 24 | tool timeout | real tool path | restore real port and retry succeeded | 0 |
| 36 | TTS failure | Piper output sink | discard failed emission and retry real response | 0 |

All three recovery events passed. The 50-turn run separately recorded five cancellation calls with stale audio count 0. Native first-token and true mid-response cancellation remain **NOT MEASURED/PARTIAL** because the installed agent returns completed responses.

## External tool boundary

A real local Worker was started and its `/health` and `/cost` routes were callable during discovery. Weather/Wikipedia are source-discovered Worker tools, but the deployed Worker ingress is Telegram-oriented and no safe local voice/session route exists. Executing them through production would require a Telegram side effect; therefore external weather/Wikipedia execution remains **BLOCKED/PARTIAL**, with no credentials or messages used.