# M5 Latency Benchmark

## Integrated metrics

The required M5 latency distributions are **NOT MEASURED** because no real HORUS runtime turn could be executed from this repository.

| Metric | State | Value |
|---|---|---|
| transcript-final -> HORUS first token p50/p95 | NOT MEASURED | runtime stream unavailable |
| HORUS first token -> first synthesized chunk p50/p95 | NOT MEASURED | runtime stream unavailable |
| user-end -> first response audio p50/p95 | NOT MEASURED | runtime stream unavailable |
| cancellation -> software silence p50/p95 | NOT MEASURED | integrated cancellation unavailable |
| tool intent -> tool result p50/p95 | BLOCKED | Telegram-only ingress; no safe authorized exchange |
| memory lookup/update latency | BLOCKED | external KV path not callable here |
| RSS start/end and drift | NOT MEASURED | no integrated run |

The M4 baseline remains the comparison reference, not an M5 result. The WAV coordinator records the required boundary timestamps once a real `RuntimePort` transport is supplied.

## No benchmark substitution

Existing M4 artifacts were not relabelled as M5 evidence. No heavy benchmark was run to conceal the missing runtime transport.
