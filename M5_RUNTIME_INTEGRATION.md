# M5 Runtime Integration

## Scope and discovery

Issue #12 requires the M4 WAV/live voice path to reach the actual HORUS runtime. The runtime discovered outside this repository is `D:/HORUS/horus-core/worker/src/index.js`.

Its real entrypoints are:

- `GET /health` and `GET /cost` on the deployed Cloudflare Worker.
- `POST /webhook/telegram`, which accepts Telegram update JSON, uses `msg.from.id`/`msg.chat.id` as identity, and sends replies through the Telegram Bot API.

Inside that entrypoint, the real paths are KV-backed `ctx:<user-id>` conversation context, `facts:<user-id>` durable memory, `tasks:<user-id>` task state, the local command handlers, `liveWeather()` using Open-Meteo, `liveWiki()` using Arabic Wikipedia, and `llm()` provider failover. Voice input is transcribed by the Worker and voice output is sent through Telegram; there is no callable streaming-token or local audio-runtime endpoint.

## Adapter implementation

`src/horus_local_voice/runtime_adapter.py` defines the exact dependency-injected `RuntimePort` needed by the discovered runtime: session resume, streamed turn, memory search/write, tool invocation, and cancellation. `VoiceRuntimeAdapter` owns local session identity, generation-based stale rejection, memory delegation, and deny-by-default tool authorization. `UnconfiguredRuntime` raises `RuntimeUnavailable`; it never substitutes a fake success.

`src/horus_local_voice/integration.py` connects WAV PCM -> chunk-fed `IncrementalTranscriber` -> runtime stream -> `PipelinedResponder` -> incremental audio emission with measured boundaries. Its test transport is explicitly a test double, not runtime evidence.

## Result

- Adapter contract and WAV coordinator: **PASS** (36 automated tests, including the end-to-end coordinator seam).
- Real HORUS runtime transport: **BLOCKED**. The Worker exposes Telegram-only ingress for turns and has no local streaming API. A direct read-only probe of the known Worker `/health` URL returned HTTP 403; no credentials or deployment changes were attempted.
- End-to-end real runtime speech: **BLOCKED**, not claimed.
- Provider, credential, billing, Meta/WhatsApp, and external-system changes: **NOT PERFORMED**.
