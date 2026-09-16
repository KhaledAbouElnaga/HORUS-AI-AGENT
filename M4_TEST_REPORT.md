# Milestone 4 Test Report

## Executed acceptance evidence

| Area | Result |
|---|---|
| Incremental STT | PASS — two genuine 30 ms chunk-fed candidates, 20 turns each, 60 partials each, all turns with multiple deduplicated hypotheses |
| Endpointing | PASS — robust 1200 ms policy, 40 trials, 0 false cuts; applied on all 50 fresh sustained streams |
| Agent streaming | PASS — Qwen2.5-1.5B streamed on 50 turns; system retained; pinned `7319` recalled at turn 50 |
| TTS streaming | PASS — Piper synthesis began from streamed phrase chunks on every turn; Arabic/English routing explicit |
| Sustained E2E | PASS — 50 fresh full-pipeline turns, 150 partials, 5 interruptions, 3 recoveries, 0 drops/duplicates/stale events/cancel failures |
| True live duplex | PASS — 10/10 overlapping active-audio input/output trials; physical stop p95 230.4233 ms, 0 stale output |
| Language expansion | PARTIAL — controlled synthetic coverage only; natural Egyptian/code-switch quality remains unproven |
| Failure/recovery | PASS — focused 9/9 runner plus earlier 11-case suite failed closed |
| Billing/provider isolation | PASS — no external runtime/provider/billing/credential changes |

## Exact current measurements

- Chunk-fed selected STT: first-partial-after-availability p50/p95 1,041.88/2,211.84 ms; final p50/p95 1,173.59/1,984.23 ms; mean WER 0.4455.
- Full-pipeline 50-turn run: STT-total p95 first/last ten 3,902.73/4,372.17 ms; agent first-token p95 2,146.98/2,746.58 ms; RSS 1,691.92→2,127.54 MB; mean WER 0.6321.
- Live duplex: callback silence p50/p95 0.0177/0.0234 ms; physical stop p50/p95 230.1882/230.4233 ms.
- Prior 40-turn first-playable p95 remains 4,404.22 ms versus M3 aggregate p95 4,146.59 ms. The latency target remains **PARTIAL / not beaten**.

## Boundary

Speech-start in the hardware duplex trial is deterministically injected while a real microphone callback and non-zero Piper output are concurrently active. Acoustic echo cancellation, human speech detector quality, subjective speaker quality, and natural conversational Egyptian/code-switch quality are **NOT MEASURED**. Raw audio was not retained.

## Commands

```bash
PYTHONPATH=src python scripts/benchmark_m4_stt_candidates.py
PYTHONPATH=src python scripts/benchmark_m4_completion.py
PYTHONPATH=src python scripts/benchmark_m4_live_duplex.py
PYTHONPATH=src python scripts/benchmark_m4_failure_recovery.py
PYTHONPATH=src python -m pytest -q
python -m compileall -q src scripts tests
```
