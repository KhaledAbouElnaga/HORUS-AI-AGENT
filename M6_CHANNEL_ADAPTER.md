# M6 Official Calling Channel Adapter

`src/horus_local_voice/whatsapp_calling.py` adds `WhatsAppCallingAdapter` as a strict channel boundary. It accepts only a normalized event envelope containing event ID, lifecycle kind, call ID, user ID, phone-number ID, and bytes at the media boundary. It does not implement a Graph client, hold tokens, configure SIP, or use WhatsApp Web.

## Behavior

- Correlates one call to `wa:<phone_number_id>:<user_id>:<call_id>` and delegates session work to a runtime port.
- Accepts `incoming → connected → media → hangup`; rejects malformed, out-of-order, duplicate, and stale events.
- On hangup increments the generation, cancels the HORUS session, and closes it; no response media is emitted by this boundary after teardown.
- Counts duplicate/stale events and returns only redacted observations; identifiers and payloads are not retained in observability.
- Leaves STT, HORUS memory/tools, TTS, and cancellation implementation with the existing runtime port rather than reimplementing them.

## Evidence state

- Adapter contract tests: **PASS**.
- Offline replay lifecycle/duplicate/stale/teardown: **PASS — SIMULATED**.
- Live official call/media: **BLOCKED** by account entitlement and human Meta gates.
