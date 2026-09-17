# M5 Tool Safety Report

## Real tool paths discovered

`worker/src/index.js` contains these real paths: local read/status commands; task persistence under `tasks:<user-id>`; live weather through Open-Meteo; and live Wikipedia through Arabic Wikipedia. The Worker routes recognized weather/Wikipedia intents before `llm()`.

## Execution result

- Three real safe categories exercised through the actual HORUS tool path: **BLOCKED**. The only external ingress is Telegram webhook and the known Worker probe returned HTTP 403. No bot token, credential, or account configuration was requested or changed.
- Read-only external/data category (weather or Wikipedia): **BLOCKED** for the same transport gate; source path is verified but not executed.
- Mutation/destructive default: **PASS at local adapter boundary**. `DenyByDefaultSafety` denies every unregistered category and `VoiceRuntimeAdapter.call_tool()` raises `PermissionError` before delegation.
- Malformed/timeout/tool exception and cancellation stale-output handling: **PASS at adapter test boundary**; **NOT MEASURED through the real Worker**.
- No unavailable tool was fabricated as exercised evidence.
