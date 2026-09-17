# M5 Runtime Integration

## Discovery evidence

Inspected the complete local HORUS installation under `D:/HORUS`, including `D:/HORUS/horus-core/app`, `worker`, `docs`, `scripts`, `backups`, and Worker config. Searched source/configs for gateway/server/listen/serve/localhost/127.0.0.1/WebSocket/RPC/API/runtime/session/agent/Telegram/polling/port.

Actual callable paths found:

- Python FastAPI app: `D:/HORUS/horus-core/app/main.py` (`app.main:app`) with `/health`, `/cost`, and Telegram webhook routes.
- Python core: `app.core.agent.handle_text`, `app.adapters.memory.store`, and `app.tasks.engine`.
- Cloudflare Worker: `worker/src/index.js`, locally run with the repository's normal `wrangler dev --local --port 8787` command. Local `/health` and `/cost` returned HTTP 200; the binding reported paid mode off and Workers AI ready. The Worker has no native local voice/session stream API and its turn route is Telegram-only.
- No HORUS process was already active before the probe. Wrangler temporarily listened on `127.0.0.1:8787` and was stopped after verification. No persistent HORUS gateway, IPC, WebSocket, RPC, polling, or other local listener was found.

## Implementation

`LocalHorusPythonPort` delegates to the installed Python HORUS agent, memory store, and task engine. `VoiceRuntimeAdapter` owns session identity and fail-closed mutation policy. Spoken aliases are normalized only to the existing `/status`, `/tasks`, and `/cost` commands. Memory utterances are routed to the installed memory store; no result is fabricated.

The M4 WAV coordinator performs real PCM -> chunk-fed faster-whisper -> local HORUS -> Piper emission. The local HORUS Python agent returns complete responses, so the transport preserves separators but records native first-token timing as NOT MEASURED and records `runtime_response_ready_ms` separately.

## Result

- Local Python HORUS callable path: **PASS**.
- Local Worker normal dev execution: **PASS for `/health` and `/cost` only**.
- Real WAV/STT/HORUS/memory/tool/TTS integrated run: **PASS for the supported command/memory path**, with native token streaming **PARTIAL**.
- Deployed Worker Telegram transport: **BLOCKED** for this voice harness; no credential or Telegram message was used.
- No provider, credential, billing, Meta/WhatsApp, deployment, or unrelated-system changes were made.