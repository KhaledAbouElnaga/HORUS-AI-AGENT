# M6 Failure and Recovery

## Reachable adapter matrix

| Case | Result | Behavior |
|---|---|---|
| duplicate control event | **PASS — SIMULATED** | Idempotent response; no second session action |
| missing/expired authorization | **BLOCKED / NOT MEASURED** | No authorized Meta state exists; no bypass attempted |
| session mismatch | **PASS — SIMULATED** | Out-of-order event is stale and ignored |
| media interruption | **NOT MEASURED** | No live media transport |
| runtime unavailable | **PASS — boundary** | Runtime exception propagates; no media fallback fabricated |
| STT/TTS failure | **NOT MEASURED for live channel** | Existing local runtime tests are separate M5 evidence |
| hangup during response | **PASS — SIMULATED** | Generation cancellation and close; stale output 0 |
| tool timeout/error | **NOT MEASURED for live channel** | No live call reaches HORUS tools |
| reconnect/retry | **PASS — SIMULATED** | Closed call can be correlated only through a new accepted lifecycle |

All simulator rows are labelled **SIMULATED**. No live Meta failure injection was possible without account access and approval.
