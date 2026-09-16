# Milestone 4 Test Report

## Executed acceptance evidence

| Area | Result |
|---|---|
| Incremental STT | PASS — 32 utterances / 64 real prefix inferences |
| Endpointing | PARTIAL — 40 trials per policy; patient policy still false-cut 11/40 |
| Agent streaming | PASS — 20 prompts plus 12-turn continuity; system retained; memory PASS |
| TTS streaming | PASS — sentence and phrase strategies, 8 runs each |
| Pipelined E2E | PASS — 40 turns, 10 per category; p95 first playable 4,404.22 ms |
| Optimization | PASS — STT beam, LLM threads, and TTS chunking measured |
| Language expansion | PARTIAL — 10 Egyptian + 10 mixed synthetic substitutes; natural data still blocked |
| Barge-in | PASS — 30/30 across generation/TTS/sink; cancel p50/p95 0.01/0.02 ms; zero stale output |
| Failure/recovery | PASS — 11/11 injected paths failed closed |
| Automated regression | PASS — 28 tests in 0.21 s |
| Billing/provider isolation | PASS — no external runtime/provider/billing changes |

## Failure injections

Executed cases: STT exception, stalled partial deadline, VAD false endpoint, LLM cancellation, empty TTS chunk, bounded audio queue overflow, duplicate and out-of-order chunks, missing voice, oversized context, and pre-allocation low-memory safeguard. Each produced the expected fail-closed result in the raw artifact.

## Known failures and limitations

- M4 did not reduce aggregate p95 below M3: first-playable p95 4,404.22 ms versus M3 E2E p95 4,146.59 ms.
- Patient endpointing still had 11/40 false cuts in the stress fixture set.
- Mixed synthetic WER remains 0.7724 with the selected route.
- Physical-speaker timing and subjective quality were not measured in this unattended run.
- Synthetic Piper fixtures do not establish spontaneous Egyptian or natural code-switch quality.

## Commands

```bash
PYTHONPATH=src python scripts/generate_m4_language_fixtures.py
PYTHONPATH=src python scripts/benchmark_m4_streaming.py
PYTHONPATH=src python -m pytest -q
python -m compileall -q src scripts tests
```
