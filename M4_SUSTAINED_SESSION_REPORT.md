# Milestone 4 Sustained Session Report

## Executed 50-turn real streaming session

Every turn executed the full local M4 path; no cached STT row was reused:

`30 ms PCM chunks -> bounded ingress -> WebRTC VAD/patient-600ms endpoint -> three incremental faster-whisper partials -> final STT -> streamed Qwen2.5-1.5B -> incremental phrase-chunked Piper`

The run covered Egyptian-labelled Arabic, MSA, English, and mixed fixtures. It included five interruptions (turns 10, 20, 30, 40, 45), three component recoveries (turns 12, 28, 44), and pinned-memory recall at turn 50.

| Metric | Exact result |
|---|---:|
| Consecutive full-pipeline turns | 50/50 |
| Incremental partial hypotheses | 150 (3 per turn) |
| Turns with multiple partials | 50/50 |
| Interruptions / cancellation failures | 5 / 0 |
| Recoveries | 3 |
| Late pinned-memory recall | PASS (`7319`) |
| Mean final STT WER | 0.6321 |
| STT total p95, turns 1–10 / 41–50 | 3,607.24 / 3,609.86 ms |
| Agent first-token p95, turns 1–10 / 41–50 | 1,332.59 / 1,402.96 ms |
| RSS start / end | 1,688.88 / 2,140.57 MB |
| RSS growth | 451.69 MB |
| Queue high-water / drops | 1 / 0 |
| Duplicate / stale events | 0 / 0 |

The increase in RSS and late-run agent latency is reported as a measured limitation, not hidden. The run used faster-whisper `tiny/int8` for repeated full-pipeline feasibility and Qwen2.5-1.5B Q4_K_M for the streamed agent. The separate chunk-fed candidate benchmark uses faster-whisper `base/int8` for quality comparison.

Raw evidence: `artifacts/m4_real_pipeline_50.json` (ignored generated artifact). Reproduce with:

```bash
PYTHONPATH=src python scripts/benchmark_m4_completion.py
```
