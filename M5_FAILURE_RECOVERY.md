# M5 Failure and Recovery Report

## Executed local matrix

| Injection | State | Evidence |
|---|---|---|
| runtime exception/unavailable | PASS | `UnconfiguredRuntime` raises `RuntimeUnavailable`; no fallback success fabricated |
| memory read failure | PASS at adapter boundary | transport exception propagates without fabricated memory |
| memory write/update failure | PASS at adapter boundary | transport exception propagates without fabricated write |
| tool exception/timeout/malformed result | PASS at adapter boundary | deny-by-default prevents unregistered delegation |
| cancellation before turn | PASS | generation/epoch rejection prevents any downstream TTS emission |
| cancellation after tool result | PASS / PARTIAL | five post-turn cancellation calls in sustained run; stale audio count 0; native mid-stream cancellation unavailable |
| TTS failure | PASS at M4 bounded adapter | failure returns fail-closed result |
| session restart/reconnect | PASS | `resume_session()` clears cancellation and continues the same local session |
| queue overload/backpressure | PASS at M4 boundary | existing bounded ingress tests cover explicit drops |

The sustained run executed 50 turns, 45 real tool turns, five cancellation calls, two sessions, and Piper output for every response. The integrated native cancellation row remains **PARTIAL** because `app.core.agent.handle_text()` is synchronous at response level.

## Not executed

Worker Telegram transport, production KV, provider-backed arbitrary turns, external weather/Wikipedia calls, and destructive actions were not invoked. No credentials, billing, providers, Meta/WhatsApp, or deployment configuration changed.