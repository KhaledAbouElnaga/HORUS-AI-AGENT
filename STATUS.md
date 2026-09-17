# Status

- **Current milestone:** Milestone 6 — official WhatsApp Calling adapter, webhook ingress, and non-SIP WebRTC/media bridge **IMPLEMENTED; CALLER AUDIBILITY NOT YET VERIFIED**.
- **Runtime:** `LocalHorusPythonPort` preserves local HORUS memory/tools while invoking Hermes/OpenCode Free through Hermes' own interpreter over a subprocess boundary; the Python 3.12 voice environment does not import Hermes dependencies.
- **Voice path:** 50 real WAV turns decoded by faster-whisper `tiny/int8`, routed through the real local HORUS command/memory paths, and synthesized by Piper. No cached transcripts were injected.
- **Memory:** 3 early facts, location correction, late recall, and two-session isolation PASS; late corrected value was `keys` as actually decoded by STT.
- **Tools:** 45 real spoken tool turns across `/status`, `/tasks`, and `/cost`; deny-by-default mutation safety PASS.
- **Sustained evidence:** 50/50 turns, 5 cancellation calls, stale audio after cancel 0, RSS 502.98→732.59 MB (+229.61 MB); runtime-response-ready p95 21.027 ms; response-ready→first-audio p95 213.577 ms; user-end→first-audio p95 3,553.642 ms; tool intent→result p95 11.46 ms.
- **Native streaming:** PARTIAL — installed Python agent returns complete responses; native first-token and mid-response cancellation remain NOT MEASURED.
- **Mixed language:** concatenated Arabic+English input was exercised, but bilingual decoded-text quality remains NOT MEASURED.
- **Regression:** 77 tests pass; compileall, tracked-file secret scan, and `git diff --check` pass.
- **Safety:** No credentials, billing, provider, Meta/WhatsApp, deployment, or unrelated-system changes.
- **Next action:** run one owner-initiated live call and require `outbound_pcm_consumed` plus increasing `outbound_rtp_stats`; caller audibility is the final Step 7 gate. PR #15 remains open; do not merge.
- **M6 official Calling:** live control ingest, SDP, ICE, `pre_accept`, `accept`, inbound audio, STT, HORUS response, TTS, and bridge queue flow are PASS. The silent-caller failure was reproduced locally: timed-out `asyncio.to_thread(queue.get)` calls remained blocked and stole later PCM; phrase-sized buffered PCM could also terminate the RTP sender through an unbound sample-rate variable. `OutputTrack` now uses one paced non-blocking consumer, fixed 48 kHz timing, explicit queue/track/RTP stages, negotiated Opus/direction checks, and sender packet/byte stats. A local two-peer aiortc regression receives decoded non-zero audio; real caller audibility remains NOT MEASURED.
