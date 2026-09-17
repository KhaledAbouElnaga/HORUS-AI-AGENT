# Status

- **Current milestone:** Milestone 5 — local runtime integration **FINAL-REVIEW READY**.
- **Runtime:** `LocalHorusPythonPort` calls the installed `D:/HORUS/horus-core/app` agent, memory store, and task engine. The Worker local-dev path also ran via `wrangler dev --local`; no production changes.
- **Voice path:** 50 real WAV turns decoded by faster-whisper `tiny/int8`, routed through the real local HORUS command/memory paths, and synthesized by Piper. No cached transcripts were injected.
- **Memory:** 3 early facts, location correction, late recall, and two-session isolation PASS; late corrected value was `keys` as actually decoded by STT.
- **Tools:** 45 real spoken tool turns across `/status`, `/tasks`, and `/cost`; deny-by-default mutation safety PASS.
- **Sustained evidence:** 50/50 turns, 5 cancellation calls, stale audio after cancel 0, RSS 502.98→732.59 MB (+229.61 MB); runtime-response-ready p95 21.027 ms; response-ready→first-audio p95 213.577 ms; user-end→first-audio p95 3,553.642 ms; tool intent→result p95 11.46 ms.
- **Native streaming:** PARTIAL — installed Python agent returns complete responses; native first-token and mid-response cancellation remain NOT MEASURED.
- **Mixed language:** concatenated Arabic+English input was exercised, but bilingual decoded-text quality remains NOT MEASURED.
- **Regression:** 41 tests pass; compileall, tracked-file secret scan, and `git diff --check` pass.
- **Safety:** No credentials, billing, provider, Meta/WhatsApp, deployment, or unrelated-system changes.
- **Next action:** final ChatGPT review. Native streamed/cancellable runtime, deployed Worker voice transport, bilingual decoded quality, and provider-backed arbitrary turns remain explicitly PARTIAL / BLOCKED / NOT MEASURED. PR #13 remains open; do not merge.
