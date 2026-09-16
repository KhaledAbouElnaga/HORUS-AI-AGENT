# Status

- **Current milestone:** Milestone 4 — streaming local voice loop and measured latency/language robustness.
- **Implementation:** Incremental STT observations, frame endpointing, streamed Qwen output, phrase/sentence Piper chunking, monotonic cancellation epochs, stale-event rejection, explicit language routing.
- **Executed evidence:** 32 streaming STT utterances; 40 endpoint trials per policy; 20 agent prompts plus 15-turn continuity; 8 TTS runs per strategy; 40 pipelined E2E turns; 50-turn sustained session with 5 interruptions and 3 recoveries; 3 optimization experiments; 20 expanded language fixtures under two routes; 30 software barge-in trials plus 10 device-level duplex trials; 9 focused required failure injections plus 11 original benchmark cases; no raw audio retained.
- **Regression:** 31 tests pass; final compile, secret scan, diff check, and tracked-scope check pass.
- **Measured limitations:** M4 first-playable p95 4,404.22 ms did not beat M3 4,146.59 ms; the robust 1200 ms endpoint benchmark had 0/40 false cuts but adds tail latency; selected mixed synthetic WER 0.7724; natural Egyptian/code-switch data remains blocked by source/license/access constraints.
- **Next action:** PR #11 is open to `main`; apply review corrections and await the next ChatGPT review. Do not merge.
- **Human input required:** None. Meta/WhatsApp, paid/billing, credentials, and existing HORUS runtime/provider routing remain untouched.

No unrelated repository or external runtime was changed.
