# M4 Failure and Recovery

## Focused required injections

`PYTHONPATH=src python scripts/benchmark_m4_failure_recovery.py` actively executed nine deterministic failure/recovery cases; **9/9 passed**.

| Case | Recovery result |
|---|---|
| Microphone/input loss | injected `OSError` caught; input session returned to listening |
| Output-device open failure | injected `OSError` caught; text-only fallback selected |
| STT worker exception | worker recovered and listening continued |
| STT timeout | bounded deadline recovered without stale output |
| Agent timeout | agent worker recovered |
| Agent cancellation | epoch advanced and stale generation was rejected |
| TTS failure | TTS worker recovered |
| Queue overload/backpressure | 2 accepted, 3 explicitly dropped, high-water 2 |
| Session restart/reconnect | stopped ingress restarted and accepted a new frame |

Raw output: ignored `artifacts/m4_failure_recovery_results.json`.

## Additional executed evidence

The primary streaming benchmark separately injected 11 fail-closed cases: STT exception, stalled partial timeout, VAD false endpoint, LLM cancellation, TTS chunk failure, queue overflow, duplicate chunk, out-of-order chunk, missing voice, oversized context, and low-memory protection. The sustained session recovered STT, agent, and TTS at turns 12, 28, and 44 and continued through turn 50. A 50-frame overload trial accepted 8 into an 8-frame queue, explicitly dropped 42, drained all accepted frames, and ended at depth zero.

## Security and isolation

- Tool-like intents: 5/5 denied; no tool side effect occurred.
- No credentials, paid endpoints, Meta/WhatsApp, provider routing, billing, or unrelated runtime configuration changed.
- Ambient microphone samples were discarded and never written.
- Cancellation epochs and sequence ledgers reject stale or duplicate output.

## Remaining limits

- Natural licensed Egyptian/code-switch conversational data remains BLOCKED; controlled substitutes are labelled.
- The selected endpoint policy needs a 1,200 ms tail, above the 900 ms target.
- Sustained RSS grew 62.07 MB; first-token p95 changed from 4,428.85 ms in turns 1-10 to 2,078.88 ms in turns 41-50, with no queue growth, dropped events, or duplicates.
- Acoustic loudspeaker stop timing and subjective quality are NOT MEASURED.
