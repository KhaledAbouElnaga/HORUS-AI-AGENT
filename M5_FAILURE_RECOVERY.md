# M5 Failure and Recovery Report

## Injection matrix

| Injection | State | Result |
|---|---|---|
| runtime unavailable | PASS | `UnconfiguredRuntime` raises `RuntimeUnavailable` (fail closed) |
| memory read failure | PASS at adapter contract | exception remains a transport error; no fabricated memory |
| memory write/update failure | PASS at adapter contract | exception remains a transport error; no fabricated write |
| tool timeout / exception / malformed result | PASS at adapter contract | no default delegation; safety boundary is preserved |
| cancellation during generation | PASS | generation mismatch raises `RuntimeCancelled` and rejects stale tokens |
| cancellation during/after tool result | NOT MEASURED integrated | real runtime transport unavailable |
| TTS failure | PASS at existing M4 boundary | bounded adapter returns fail-closed result |
| restart/reconnect | PASS at adapter lifecycle seam | session resume is an explicit port operation |
| queue overload/backpressure | PASS at existing M4 boundary | bounded ingress records drops |

The PASS rows are local contract/error-path tests, not proof of external HORUS execution. No stale tool or TTS output is claimed for the blocked integrated path.

## Blocker

The discovered Worker has Telegram-only `POST /webhook/telegram` ingress, KV-backed state, and Telegram Bot API egress. It has no local callable stream/session API. A read-only request to the known deployment `/health` endpoint returned HTTP 403. No token, login, account approval, billing, provider, or deployment change was attempted.
