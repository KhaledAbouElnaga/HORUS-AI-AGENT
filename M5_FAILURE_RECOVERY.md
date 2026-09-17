# M5 Failure and Recovery Report

## Injection matrix

| Injection | State | Result |
|---|---|---|
| runtime unavailable | PASS | `UnconfiguredRuntime` raises `RuntimeUnavailable` |
| memory read failure | PASS at adapter contract | transport exception is propagated; no fabricated memory |
| memory write/update failure | PASS at adapter contract | transport exception is propagated; no fabricated write |
| tool timeout / exception / malformed result | PASS at adapter contract | fail-closed safety boundary remains in force |
| cancellation during generation | PASS at adapter contract | generation mismatch raises `RuntimeCancelled` |
| cancellation during/after tool result | PARTIAL | stale rejection tested; native local agent cancellation unavailable |
| TTS failure | PASS at M4 boundary | bounded adapter returns fail-closed result |
| session restart/reconnect | PASS at adapter lifecycle seam | `resume_session` is explicit |
| queue overload/backpressure | PASS at M4 boundary | bounded ingress records drops |

The local Worker normal tooling was exercised with `wrangler dev --local`; `/health` and `/cost` passed. Its Telegram turn route was not used as a message transport because it requires bot credentials and sends Telegram egress. The local Python core path was exercised without secrets.

PASS rows are real local code or contract tests, not proof of native streaming cancellation. Integrated M5 recovery remains **NOT MEASURED**.