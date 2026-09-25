# Status

- **Current milestone:** Milestone 6 — official WhatsApp Calling adapter, webhook ingress, and non-SIP WebRTC/media bridge **IMPLEMENTED; CLEAR BILINGUAL LIVE RESPONSE NOT YET VERIFIED**.
- **Runtime:** `LocalHorusPythonPort` preserves local HORUS memory/tools while invoking Hermes/OpenCode Free through Hermes' own interpreter over a subprocess boundary; the Python 3.12 voice environment does not import Hermes dependencies.
- **Voice path:** live RTP/media is caller-heard PASS; conversational tuning now uses base multilingual final STT, patient endpointing, latest-turn policy, and temporary half-duplex echo suppression.
- **Memory:** 3 early facts, location correction, late recall, and two-session isolation PASS; late corrected value was `keys` as actually decoded by STT.
- **Tools:** 45 real spoken tool turns across `/status`, `/tasks`, and `/cost`; deny-by-default mutation safety PASS.
- **Sustained evidence:** 50/50 turns, 5 cancellation calls, stale audio after cancel 0, RSS 502.98→732.59 MB (+229.61 MB); runtime-response-ready p95 21.027 ms; response-ready→first-audio p95 213.577 ms; user-end→first-audio p95 3,553.642 ms; tool intent→result p95 11.46 ms.
- **Native streaming:** PARTIAL — installed Python agent returns complete responses; native first-token and mid-response cancellation remain NOT MEASURED.
- **Mixed language:** multilingual `base/int8`, beam 5: auto `ar/en` is accepted only at ≥0.60 confidence; lower-confidence or unsupported detection compares forced Arabic/English candidates by decode quality and script plausibility. Natural bilingual quality remains NOT MEASURED.
- **Regression:** 87 tests pass; compileall, tracked-file secret scan, and `git diff --check` pass.
- **Safety:** No credentials, billing, provider, Meta/WhatsApp, deployment, or unrelated-system changes.
- **Next action:** run one owner-initiated live call with `STT_MODEL=base` and `STT_BEAM_SIZE=5`; the caller must hear one clear Arabic or English response. PR #15 remains open; do not merge.
- **M6 official Calling:** live control ingest, SDP, ICE, `pre_accept`, `accept`, inbound audio, STT, HORUS response, TTS, Opus/sendrecv, OutputTrack delivery, and RTP packet/byte transmission are PASS per owner report. The current fixes force UTF-8 RPC I/O on Windows, prevent Arabic `cp1252` decode failures, select final endpointed multilingual STT with safe Arabic fallback, and log `tts_route=ar|en` plus non-empty PCM size. Clear, understandable Arabic or English caller experience remains NOT MEASURED.
