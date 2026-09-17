# M5 Latency Benchmark

## Integrated metrics

The required M5 integrated latency distributions are **NOT MEASURED**. The installed Python HORUS agent returns a complete response and the Worker has no local voice/session stream endpoint, so timing its word chunking would misrepresent runtime latency.

| Metric | State | Value |
|---|---|---|
| transcript-final -> HORUS first token p50/p95 | NOT MEASURED | no native runtime stream |
| HORUS first token -> first synthesized chunk p50/p95 | NOT MEASURED | no native runtime stream |
| user-end -> first response audio p50/p95 | NOT MEASURED | no valid integrated audio turn |
| cancellation -> software silence p50/p95 | NOT MEASURED | native cancellation unavailable |
| tool intent -> tool result p50/p95 | PARTIAL | local `/status`, `/tasks`, `/cost` calls execute; no 10-turn distribution |
| memory lookup/update latency | PARTIAL | local store calls execute; production KV not exercised |
| RSS start/end and drift | NOT MEASURED | no sustained integrated run |

M4 measurements remain the comparison baseline. No heavy M5 benchmark was run without a valid integrated stream.