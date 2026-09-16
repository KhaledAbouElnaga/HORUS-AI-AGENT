# Status

- **Current milestone:** Milestone 4 — streaming local voice loop and measured latency/language robustness; PR #11 review corrections executed.
- **Implementation:** 30 ms bounded audio ingress, WebRTC VAD/endpointing, genuine multi-hypothesis chunk-fed STT, streamed Qwen output, incremental Piper phrase synthesis, monotonic cancellation, stale-event rejection, explicit Arabic/English routing, and session lifecycle recovery.
- **Chunk-fed STT evidence:** two `base/int8` candidates × 20 turns after warm-up; each produced 60 partial hypotheses and every turn had multiple partials. Selected candidate first-partial-after-availability p95 2,211.84 ms, final p95 1,984.23 ms, mean WER 0.4455, 0 queue drops.
- **Sustained evidence:** 50 consecutive fresh full-pipeline turns, 150 partials, 5 interruptions, 3 recoveries, late pinned-memory recall PASS, 0 drops/duplicates/stale events/cancel failures. RSS 1,688.88→2,140.57 MB; STT-total p95 3,607.24→3,609.86 ms; agent first-token p95 1,332.59→1,402.96 ms.
- **Live duplex evidence:** 10/10 overlapping Windows input/output trials with active non-zero Piper speech. Injected speech-start while microphone callback was active produced callback-silence p95 0.0234 ms and physical stream-stop p95 230.4233 ms; 0 stale output samples; no raw microphone audio retained.
- **Failure evidence:** focused 9/9 failure/recovery runner plus earlier 11-case suite fail closed.
- **Regression:** 31 tests pass; compileall, artifact acceptance assertions, secret scan, and `git diff --check` pass.
- **Measured limitations:** M4 still does not beat M3 aggregate latency; RSS grew 451.69 MB across the full-pipeline run; full-pipeline tiny STT mean WER was 0.6321; patient-600ms endpointing (11/40 false cuts) uses a 600 ms end-silence window; natural Egyptian/code-switch and acoustic echo/human interruption quality remain NOT MEASURED.
- **Next action:** update PR #11 on the same branch, post exact review-ready results, and await ChatGPT review. Do not merge.
- **Human input required:** None. Meta/WhatsApp, paid/billing, credentials, existing HORUS providers/routing, and unrelated systems remain untouched.
