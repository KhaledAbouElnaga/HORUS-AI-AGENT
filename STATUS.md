# Status

- **Current milestone:** Milestone 5 — runtime/memory/tool integration started; external HORUS transport gate documented.
- **M5 implementation:** `runtime_adapter.py` defines the real-runtime port with session identity, memory delegation, deny-by-default tools, and generation cancellation; `integration.py` wires WAV PCM through chunk-fed STT, streamed runtime output, and incremental TTS emission.
- **M5 runtime discovery:** `D:/HORUS/horus-core/worker/src/index.js` exposes Telegram-only `POST /webhook/telegram` plus `/health` and `/cost`; KV stores `ctx:<user-id>`, `facts:<user-id>`, and `tasks:<user-id>`. No callable local streaming/session API exists.
- **M5 status:** Adapter/WAV seams PASS in local tests; real runtime end-to-end, real memory continuity, three real tool categories, sustained 50-turn integration, and integrated latency/resource evidence are BLOCKED or NOT MEASURED pending a callable runtime transport. No fake evidence is used.
- **Regression:** 36 tests pass; compileall and `git diff --check` pass. Input device probe failed with PortAudio host error; output probe passed.
- **Safety:** No billing, credentials, providers, Meta/WhatsApp configuration, deployment, or unrelated systems changed.
- **Next action:** Provide a permitted callable HORUS runtime transport or endpoint; do not bypass the Telegram/credential boundary.
