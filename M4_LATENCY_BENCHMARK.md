# Milestone 4 Latency Benchmark

All runs were CPU-only on the same Windows host. Raw rows are in ignored `artifacts/m4_streaming_results.json`.

## Streaming components

- Incremental STT: 32 utterances, 64 real prefix inferences. First partial availability p50/p95 5,509.37/9,040.10 ms (includes reaching the 50% audio prefix); finalization compute p50/p95 1,229.04/1,594.05 ms; mean WER 0.3109; 32 partial revisions.
- Streamed Qwen: 20 prompts. First token p50/p95 99.38/114.92 ms; first phrase 381.03/567.10 ms; total 608.88/1,176.61 ms; throughput 31.51/34.85 tokens/s. A 12-turn bounded scenario retained the system instruction and recalled pinned value `7319` at turn 12.
- Piper chunking: 8 runs per strategy. Sentence first playable p50/p95 554.16/723.59 ms, RTF p50/p95 0.11/0.31. Phrase first playable 575.77/714.04 ms, RTF 0.11/0.17. Phrase has the better measured worst-case RTF but not the better p50 first audio.

## True pipelined E2E, 40 turns

The benchmark starts chunk synthesis as soon as streamed model text reaches punctuation or 60 characters; it does not wait for completion.

| Speech-end metric | p50 | p95 |
|---|---:|---:|
| STT final | 1,118.52 ms | 1,594.05 ms |
| Agent first token | 3,515.97 ms | 4,054.34 ms |
| First token -> first playable | 341.40 ms | 393.03 ms |
| First playable audio | 3,848.36 ms | 4,404.22 ms |
| Pipeline total | 3,873.33 ms | 4,427.31 ms |

| Category | Turns | Mean WER | First playable p50 / p95 |
|---|---:|---:|---:|
| Egyptian-labelled | 10 | 0.4108 | 4,154.22 / 4,485.70 ms |
| MSA | 10 | 0.1667 | 3,801.21 / 4,026.12 ms |
| English | 10 | 0.0749 | 4,095.24 / 4,376.15 ms |
| Mixed synthetic | 10 | 0.8125 | 1,506.30 / 3,931.90 ms |

M3 aggregate E2E p95 was 4,146.59 ms. M4 first-playable p95 is 4,404.22 ms and total p95 is 4,427.31 ms, so this implementation did **not** beat M3 aggregate latency. It adds real incremental results and early agent-to-TTS overlap, but long rolling context and prefix inference offset that gain.

## Three optimization experiments

1. STT beam 1 vs 5 on four files: beam 1 p50 886.44 ms / WER 0.4222; beam 5 p50 1,066.45 ms / WER 0.3500. Keep beam 5 final; beam 1 is partial-only.
2. Qwen threads 4 vs 8 over three prompts: total p50 459.72 vs 452.63 ms; 8 threads retained as default. RSS was effectively equal (~2,294 MB while loaded).
3. Sentence vs phrase TTS: phrase reduced worst-case RTF from 0.31 to 0.17; use phrase chunks capped at 55–60 characters with sentence fallback.
