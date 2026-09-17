# M5 Sustained Integration Report

## Required run

A real >=50-turn or 15-minute integrated voice run remains **BLOCKED**. The local Python HORUS agent is callable for direct commands, but arbitrary turns require the provider router and no provider key is configured; it also returns complete responses rather than native streaming deltas. The local Worker has Workers AI available in local-dev mode, but its only turn route is Telegram webhook with Telegram egress, not a local voice/session API.

## Evidence status

| Requirement | State | Evidence |
|---|---|---|
| Real callable HORUS turn | PASS / PARTIAL | Local `app.core.agent.handle_text('/status')` executed; native streaming unavailable |
| Arabic, English, mixed integrated turns | NOT MEASURED | No native local runtime stream |
| >=5 interruptions | NOT MEASURED | No cancellable runtime stream |
| >=3 recovery events | NOT MEASURED | No integrated runtime session |
| >=10 real tool-mediated turns | PARTIAL | Three real local categories exercised; 10-turn integrated runtime not executed |
| Three facts, correction, late recall, two sessions | PASS | Real local memory evidence script passed; production KV not exercised |
| Queue/drop/duplicate/stale metrics | PASS / NOT MEASURED | Adapter/M4 seam tests pass; no sustained runtime stream |
| RSS and latency drift | NOT MEASURED | No valid integrated run |

No cached M4 rows were relabelled as M5 evidence.