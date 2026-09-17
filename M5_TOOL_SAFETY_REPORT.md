# M5 Tool Safety Report

## Real categories exercised

`LocalHorusPythonPort.invoke_tool()` delegates to the installed HORUS `app.core.agent.handle_text()` command path. The sustained run first decoded spoken WAV input with faster-whisper, normalized only recognized aliases, invoked the real command handler, and passed the resulting response to Piper.

The run exercised 45 real tool-mediated turns across exactly three categories:

- `/status` — system health/status response
- `/tasks` — active task listing
- `/cost` — cost response from the installed router accounting path

The three categories are recorded in `artifacts/m5_sustained_local.json`. The Worker-only Open-Meteo and Arabic Wikipedia paths were source-discovered but not executed because their only turn ingress is Telegram and no authorized transport was used.

## Safety

- Mutation/destructive default: **PASS** — `DenyByDefaultSafety` rejects unregistered categories before delegation.
- Tool result incorporated into spoken output: **PASS** for the three local command categories; Piper synthesized every resulting response.
- Malformed/timeout/exception and stale-output handling: **PASS at adapter boundary; PARTIAL integrated** because the installed agent has no interruptible native stream.
- No destructive command, credential, billing, provider, Meta/WhatsApp, or deployment action was attempted.