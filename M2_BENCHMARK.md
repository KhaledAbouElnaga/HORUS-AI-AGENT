## Real local benchmark

| Path | Result |
|---|---:|
| STT | 20 turns; p50 959.62 ms, p95 1075.13 ms, max 1089.04 ms |
| Agent first output | p50/p95 0.001 ms (deterministic in-process adapter) |
| TTS first-audio | p50 233.20 ms, p95 368.06 ms, max 420.06 ms |
| End-to-end | p50 1199.54 ms, p95 1428.56 ms, max 1469.53 ms |
| Model load | 965.50 ms warm-cache load in latest run; first cold run 25,406.15 ms |
| Voice load | 3519.07 ms for two Piper voices |
| Process RSS | 481.3 MB at completion; CPU path, no GPU |
| WER proxy | mean 0.5411 over 20 turns (8 fixture types) |
| Barge-in | 10/10 active-chunk cancellations; min/median/p95 0.0 ms at sink boundary; speaker hardware latency not measured |
| Session | 20 real audio turns retained; 10-turn continuity assertion PASS |

These measurements are local CPU/harness measurements, not production or microphone latency. The Arabic clips are labeled Egyptian-Arabic dataset samples but are read benchmark sentences; Egyptian conversational quality remains unproven.


| Measurement | Observed value | Scope/limitation |
|---|---:|---|
| Harness startup + fixture load | 51.09 ms | One local run; includes Python startup and `runpy` overhead |
| Python peak traced allocations | 1,884.8 KiB | `tracemalloc` Python allocations, not total process RSS |
| Seven fixture turns end-to-end | 0.04 ms | Mock/deterministic path, not real audio or model latency |
| Model download/storage | faster-whisper tiny + 2 Piper voices | Cached local models; exact file sizes in local voice/model directories, not committed |
| CPU/GPU | CPU-only; process RSS 428.7 MB; sample CPU 1362.4% across logical cores | No GPU used |
| Largest bottleneck | STT p95 818.60 ms; cold model load 25.41 s | CPU tiny model, 20-turn run |

The first table is the real local pipeline; the second retains deterministic harness baselines. These are not production or microphone latency claims.
