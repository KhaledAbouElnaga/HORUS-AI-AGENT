# M5 Memory and Session Report

## Contract

The real Worker stores short conversation context in `ctx:<user-id>` (last 10 messages, seven-day TTL) and durable facts in `facts:<user-id>` (last 50 facts). `/memory`, `افتكر`, `فاكر`, and `انسى` are handled in `worker/src/index.js`; `/forget` clears conversation context rather than durable facts.

The local adapter exposes `lookup_memory()` and `write_memory()` and scopes every request to an explicitly opened unique session ID.

## Execution result

- Three early facts recalled late: **BLOCKED** — requires a real callable HORUS transport/Telegram exchange.
- One correction/update: **BLOCKED** — the Worker has append-style `facts` and no exposed update endpoint.
- Forget/override: **BLOCKED** for the same external transport gate; source inspection confirms `/forget` semantics above.
- Isolation between two session IDs: **PASS at adapter contract level**, covered by automated tests using an explicitly named recording transport; **NOT MEASURED against the real Worker**.
- No cross-session data is fabricated or reported as real evidence.
