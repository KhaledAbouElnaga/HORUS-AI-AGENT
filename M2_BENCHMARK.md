# Milestone 2 Benchmark

**Host:** Windows; deterministic Python harness; no speech model downloaded.

| Measurement | Observed value | Scope/limitation |
|---|---:|---|
| Harness startup + fixture load | 51.09 ms | One local run; includes Python startup and `runpy` overhead |
| Python peak traced allocations | 1,884.8 KiB | `tracemalloc` Python allocations, not total process RSS |
| Seven fixture turns end-to-end | 0.04 ms | Mock/deterministic path, not real audio or model latency |
| Model download/storage | 0 B | No model was installed |
| CPU/GPU | CPU-only deterministic path | No GPU/model benchmark performed |
| Largest bottleneck | Not applicable yet | Real STT/TTS benchmark is a next milestone task |

These numbers are harness baselines only and must not be used as realtime speech performance claims.
