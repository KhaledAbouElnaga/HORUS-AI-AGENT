# M6 Calling Test Report

## SIMULATED replay

`tests/test_whatsapp_calling.py` replays a normalized documented-lifecycle contract: incoming, connected, media, and hangup. It proves session correlation, media delegation, teardown, duplicate idempotency, malformed-event rejection, and out-of-order media rejection. This evidence is explicitly **SIMULATED**, not a live WhatsApp call.

## Live call

**BLOCKED / NOT EXECUTED.** No Meta account entitlement, authorized phone number, webhook subscription, SIP endpoint, or approved test number is available. No Telegram/WhatsApp message or call was sent. Therefore Arabic, English, mixed, 10-turn, tool, memory, barge-in, reconnect, and live media metrics are **NOT MEASURED**, not inferred from the local M4/M5 runs.
