# Status

- **Current milestone:** Milestone 4 — streaming local voice loop and measured latency/language robustness.
- **Implementation:** Incremental STT observations, frame endpointing, streamed Qwen output, phrase/sentence Piper chunking, monotonic cancellation epochs, stale-event rejection, explicit language routing.
- **Executed evidence:** 32 streaming STT utterances; 40 endpoint trials per policy; 20 agent prompts plus 12-turn continuity; 8 TTS runs per strategy; 40 pipelined E2E turns; 3 optimization experiments; 20 expanded language fixtures under two routes; 30 barge-in trials; 11 failure injections; 10 unretained microphone captures.
- **Regression:** 28 tests pass. Final compile, secret scan, diff check, and tracked-scope check are required immediately before PR.
- **Measured limitations:** M4 first-playable p95 4,404.22 ms did not beat M3 4,146.59 ms; patient endpointing false-cut 11/40 stress trials; selected mixed synthetic WER 0.7724; natural Egyptian/code-switch data remains blocked by source/license/access constraints.
- **Next action:** Open one PR to `main` and await ChatGPT review; do not merge.
- **Human input required:** None. Meta/WhatsApp, paid/billing, credentials, and existing HORUS runtime/provider routing remain untouched.

No unrelated repository or external runtime was changed.
