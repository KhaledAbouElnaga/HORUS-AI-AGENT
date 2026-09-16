## Real local benchmark

| Path | Result |
|---|---:|
| STT | 20 turns; p50 751.22 ms, p95 818.60 ms, max 832.83 ms |
| Agent first output | p50/p95 0.00 ms (deterministic in-process adapter) |
| TTS first-audio proxy | p50 75.75 ms, p95 88.03 ms, max 99.84 ms |
| End-to-end | p50 830.91 ms, p95 906.27 ms, max 920.88 ms |
| Model load | 25,406.15 ms cold load from first STT run |
| Process RSS | 428.7 MB at completion; CPU path, no GPU |
| WER proxy | mean 0.4923 over 20 repeated fixture turns |
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
