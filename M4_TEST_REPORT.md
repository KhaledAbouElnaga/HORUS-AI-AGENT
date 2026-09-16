# Milestone 4 Test Report

## Executed acceptance evidence

| Area | Result |
|---|---|
| Incremental STT | PASS — 32 utterances / 64 real prefix inferences |
| Endpointing | PASS — selected robust-1200ms policy: 40 trials, 0 false cuts, p95 decision 0.0418 ms; fast/patient tradeoff retained as comparison evidence |
| Agent streaming | PASS — 20 prompts plus 15-turn continuity; system retained; memory PASS |
| TTS streaming | PASS — sentence and phrase strategies, 8 runs each |
| Pipelined E2E | PASS — 40 turns, 10 per category; p95 first playable 4,404.22 ms |
| Sustained duplex | PASS — 50 consecutive turns, 5 interruptions, 3 recoveries, 0 dropped/duplicated events |
| Device-level duplex interruption | PASS — 10 input/output stream trials; silent-output stop p95 63.57 ms, no stale resume |
| Optimization | PASS — STT beam, LLM threads, and TTS chunking measured |
| Language expansion | PARTIAL — 10 Egyptian + 10 mixed synthetic substitutes; natural data still blocked |
| Barge-in | PASS — 30/30 across generation/TTS/sink; cancel p50/p95 0.01/0.02 ms; zero stale output |
| Failure/recovery | PASS — 9/9 focused required injections plus 11/11 original benchmark cases failed closed |
| Automated regression | PASS — 31 tests |
| Billing/provider isolation | PASS — no external runtime/provider/billing changes |

## Failure injections

The focused run executed microphone/input loss, output-device open failure, STT exception and timeout, agent timeout and cancellation, TTS failure, queue overload/backpressure, and session restart/reconnect: 9/9 passed. The original benchmark also executed 11 fail-closed cases covering false endpointing, duplicate/out-of-order chunks, missing voice, oversized context, and low-memory protection.

## Known failures and limitations

- M4 did not reduce aggregate p95 below M3: first-playable p95 4,404.22 ms versus M3 E2E p95 4,146.59 ms.
- The selected robust endpoint policy had 0/40 false cuts, but its 1,200 ms tail misses the 900 ms target; faster policies had 25/40 and 11/40 false cuts.
- Mixed synthetic WER remains 0.7724 with the selected route.
- Silent output-stream stop timing was measured; acoustic loudspeaker stop time and subjective quality were NOT MEASURED.
- Synthetic Piper fixtures do not establish spontaneous Egyptian or natural code-switch quality.

## Commands

```bash
PYTHONPATH=src python scripts/generate_m4_language_fixtures.py
PYTHONPATH=src python scripts/benchmark_m4_streaming.py
PYTHONPATH=src python scripts/benchmark_m4_stt_candidates.py
PYTHONPATH=src python scripts/benchmark_m4_completion.py
PYTHONPATH=src python scripts/benchmark_m4_failure_recovery.py
PYTHONPATH=src python -m pytest -q
python -m compileall -q src scripts tests
```
