# M5 Sustained Integration Report

## Required run

A real >=50-turn integrated run was **BLOCKED**, not replaced with cached rows or the M4 deterministic harness. The missing link is a callable HORUS runtime transport: the deployed Worker accepts Telegram updates and sends Telegram replies, but does not expose streaming local-runtime/session/tool endpoints. No credentials or external configuration were changed to bypass that boundary.

## Required evidence status

| Requirement | State | Evidence |
|---|---|---|
| 50 consecutive integrated turns / 15 minutes | BLOCKED | No real runtime transport |
| Arabic, English, mixed | NOT MEASURED | M4 fixtures exist; not M5 runtime evidence |
| >=5 interruptions | NOT MEASURED | Runtime cancellation endpoint unavailable |
| >=3 recovery events | NOT MEASURED | No integrated runtime execution |
| >=10 real tool turns | BLOCKED | Telegram-only Worker ingress; no authorized exchange |
| late memory recall and two session IDs | BLOCKED | KV is keyed by Telegram user ID; no callable test session API |
| queue/drop/duplicate/stale metrics | PASS at local adapter tests; NOT MEASURED integrated | 36-test suite |
| RSS and latency drift | NOT MEASURED | No integrated run |

No sustained M5 result is claimed.
