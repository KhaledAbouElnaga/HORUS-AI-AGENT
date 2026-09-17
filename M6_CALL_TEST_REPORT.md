# M6 Calling Test Report

## SIMULATED replay

`tests/test_whatsapp_calling.py` replays a normalized documented-lifecycle contract: incoming, connected, media, and hangup. It proves session correlation, media delegation, teardown, duplicate idempotency, malformed-event rejection, and out-of-order media rejection. This evidence is explicitly **SIMULATED**, not a live WhatsApp call.

## Prepared external ingress probe

Temporary public URL: `https://cold-jokes-make.loca.lt/webhooks/whatsapp/calling`.

- GET challenge: **PASS**, HTTP 200; challenge returned correctly.
- Invalid-signature POST: **PASS**, HTTP 403; no parser/runtime side effect.
- The tunnel and local server are reversible probe infrastructure, not production.

## Live call

**BLOCKED / NOT EXECUTED.** Calling is enabled on the Meta test number and the `calls` webhook sample test succeeded per owner report. The parser now accepts the documented v26 sample shape. A real inbound call still requires the public callback to be configured with the account and an SDP/WebRTC media endpoint; no WhatsApp call was initiated.
