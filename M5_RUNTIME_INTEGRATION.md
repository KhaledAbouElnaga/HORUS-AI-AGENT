# M5 Runtime Integration

## Exhaustive discovery

Inspected:

- `D:/HORUS/horus-core/app/main.py`, `app/core/agent.py`, `app/adapters/memory/store.py`, `app/adapters/llm/router.py`, `app/tasks/engine.py`, and `app/core/config.py`.
- `D:/HORUS/horus-core/worker/src/index.js` and `worker/wrangler.toml`.
- `D:/HORUS` runtime/config/backup folders and `C:/Users/khale/Documents/Absher-Bot` for gateway, server, listen, localhost, WebSocket, RPC, API, runtime, session, agent, Telegram, polling, and port references.
- Running-process candidates and all TCP listening ports; no identifiable HORUS gateway process was mapped by `tasklist`. Port `8787` was created by the local Wrangler Worker during this pass.

## Actual callable paths

The local Python HORUS application is callable in-process from `D:/HORUS/horus-core/app`:

- `app.main:app` exposes real FastAPI `/health`, `/cost`, and `POST /webhook/telegram` entrypoints.
- `app.core.agent.handle_text(text, context)` is the real agent loop.
- `app.adapters.memory.store` is the real local memory store (`remember`, `recall`, `forget`).
- `app.tasks.engine` is the real task state path.
- `app.adapters.llm.router` is the real provider router, but this environment has no configured provider key and paid mode is off.

`LocalHorusPythonPort` calls those modules directly; it does not reimplement them. The local runtime returns a completed response, not native token deltas, so word chunks are explicitly marked transport chunks and not streaming evidence.

The exact Worker also runs through its normal local tooling: `wrangler dev --local --port 8787 --show-interactive-dev-session=false`. Real local-dev checks returned `/health` HTTP 200 with Workers AI ready and `/cost` HTTP 200 with paid mode off. This is local Worker execution, not deployed execution. The Worker still exposes Telegram-only turn ingress/egress and no local session-stream API.

## Result

- Local real HORUS core adapter: **PASS** for callable agent commands, memory, task/status/cost paths.
- WAV -> chunk-fed STT -> runtime -> incremental TTS coordinator: **PASS** at the transport boundary; arbitrary LLM turns remain provider-dependent.
- Native streamed HORUS output/cancellation: **PARTIAL**; the Python core has no streaming API and cancellation is not interruptible during its synchronous `handle_text` call.
- Real end-to-end microphone/WAV voice with native HORUS streaming: **BLOCKED**.
- No provider, credential, billing, Meta/WhatsApp, deployment, or unrelated-system changes were made.