# Status

- **Current milestone:** Milestone 6 — official WhatsApp Calling adapter and non-SIP WebRTC/RTP bridge are implemented; Roadmap Step 7 now uses an OpenAI Realtime acceptance backend and still needs its live API preflight plus one final owner call.
- **Voice backends:** `HORUS_VOICE_BACKEND=legacy|realtime` defaults to `legacy`. Legacy keeps Whisper/local VAD/Hermes/Piper available; Step 7 acceptance selects `realtime`, which streams PCM16 to `gpt-realtime-2.1` and does not load those legacy conversational components.
- **Realtime media path:** proven WhatsApp PCM 48 kHz → PCM16 24 kHz Realtime WebSocket → PCM16 48 kHz → unchanged OutputTrack/Opus/RTP sender. Server semantic VAD owns endpointing; temporary playout-tail input suppression favors stability over barge-in.
- **Realtime identity/tools:** concise Egyptian-Arabic HORUS identity instructions preserve English; the model can call a deny-by-default local `get_horus_status` function and continue in the same session without Hermes conversational generation.
- **Realtime safety:** one bridge/WebSocket per call, one active call at a time, explicit connect/first-audio/tool/response timeouts, controlled Arabic fallback request while the socket remains usable, and bounded teardown/fresh-session regression coverage.
- **Automated preflight:** offline regressions and deterministic Arabic fixture generation pass. Live authentication/session/audio/semantic/tool/latency preflight remains **BLOCKED in the Hermes process only** because `OPENAI_API_KEY` is not inherited; run `scripts/preflight_openai_realtime.py` from the already-keyed owner terminal before any WhatsApp call.
- **WhatsApp acceptance:** caller-heard RTP is already PASS from the legacy transport proof. Do not claim Realtime WhatsApp acceptance until live preflight passes and Khaled completes the single final Arabic call.
- **Memory:** 3 early facts, location correction, late recall, and two-session isolation PASS; late corrected value was `keys` as actually decoded by STT.
- **Tools:** 45 real spoken tool turns across `/status`, `/tasks`, and `/cost`; deny-by-default mutation safety PASS.
- **Sustained evidence:** 50/50 turns, 5 cancellation calls, stale audio after cancel 0, RSS 502.98→732.59 MB (+229.61 MB); runtime-response-ready p95 21.027 ms; response-ready→first-audio p95 213.577 ms; user-end→first-audio p95 3,553.642 ms; tool intent→result p95 11.46 ms.
- **Native streaming:** PARTIAL — installed Python agent returns complete responses; native first-token and mid-response cancellation remain NOT MEASURED.
- **Legacy mixed language:** multilingual `base/int8`, beam 5 remains available only under `HORUS_VOICE_BACKEND=legacy`; it is no longer the Step 7 acceptance path.
- **Regression:** 101 tests pass; compileall, tracked-file secret scan, and `git diff --check` pass.
- **Safety:** No credentials, billing, provider, Meta/WhatsApp, deployment, or unrelated-system changes. `OPENAI_API_KEY` is read only from the process environment and is never logged or persisted.
- **Next action:** run the single live Realtime preflight from the terminal that already has `OPENAI_API_KEY`. Only if it passes, run one final WhatsApp acceptance call. PR #15 remains open; do not merge.
- **M6 official Calling:** Meta control, SDP/ICE, inbound media, caller-heard OutputTrack/Opus/RTP delivery, and RTP counters are proven. The new Realtime backend reuses that transport unchanged; clear Realtime Arabic caller experience remains **NOT MEASURED** until the final owner call.
