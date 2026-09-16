# Milestone 1 Acceptance Tests

## Research/specification evidence

| ID | Result | Evidence |
|---|---|---|
| M1-R1 | PASS | `RESEARCH_WHATSAPP_VOICE.md`, Capability classification: official API, webhooks, SIP boundary, private protocol, third-party bridge, local prototype, fallback |
| M1-R2 | PASS | `RESEARCH_WHATSAPP_VOICE.md`, access date and Sources [1]–[15]; strict citation verification passed |
| M1-R3 | PASS | `RESEARCH_WHATSAPP_VOICE.md`, Official Calling media-path verification and Open research gates; eligibility, review, pricing, and live account contract are explicit gates |
| M1-R4 | PASS | Git diff contains documentation only; no Meta account/billing/credential/runtime change; secret scan passed |
| M1-R5 | PASS | `RESEARCH_WHATSAPP_VOICE.md`, Concrete local pipeline candidates and preferred Milestone-2 stack |
| M1-R6 | BLOCKED | Account entitlement, regional eligibility, approval, quotas, and live negotiated media behavior require Meta account access; no account action is authorized in this milestone |
| M1-R7 | PASS | `ARCHITECTURE.md` decision matrix and `ACCEPTANCE_TESTS.md` local test matrix define measurable prototype validation before channel integration |

## Milestone 2 evidence

| ID | Result | Evidence |
|---|---|---|
| M2-01 | PASS | `tests/test_harness.py` — scripted turns, metrics, and fixture languages |
| M2-02 | PASS | `test_barge_in_cancels_stale_tts_output` |
| M2-03 | PASS | `test_context_survives_ten_turns` |
| M2-04 | PASS | `test_duplicate_and_out_of_order_events_are_idempotent` |
| M2-05 | PASS | `test_channel_failure_enters_fallback` |
| M2-06 | PASS | `test_tool_calls_fail_closed_and_are_audited` |
| M2-07 | PASS | `python -m compileall -q src tests` and secret scan |
| M2-08 | PASS | `scripts/run_real_pipeline.py` executed 20 real WAV -> faster-whisper -> deterministic agent -> Piper turns; 20/20 completed |
| M2-09 | BLOCKED | Meta/WhatsApp integration intentionally deferred |
| M2-10 | PASS | `scripts/benchmark_barge_in.py`: 10 active-chunk cancellation runs; stale audio sink stopped |
| M2-11 | PASS | `scripts/download_fixtures.py` creates 3 Egyptian-Arabic, 2 formal-Arabic-text, 2 English, and 1 composed mixed WAV fixture |
| M2-12 | NOT YET MEASURED | Physical microphone/speaker path and hardware interruption latency |
| M2-13 | NOT YET MEASURED | Real local agent model; deterministic agent used because no suitable pre-existing local runtime was found |
| M2-14 | PASS | Recovery recorded for wrong dataset config, float WAV, and TTS ONNX allocation failure |

## Milestone 3 evidence

| ID | Result | Evidence |
|---|---|---|
| M3-01 | PASS | `M3_BENCHMARK.md`: tiny/int8 auto, base/int8 auto, and base/int8 forced-Arabic beam5; 72 measured transcriptions plus warm-ups on the same 8 fixtures |
| M3-02 | PASS | Piper kareem-medium and kareem-low each synthesized 7 phrases; the low alternative did not outperform medium; English E2E output uses lessac-medium |
| M3-03 | PASS/PARTIAL | Qwen2.5 0.5B and 1.5B ran through llama.cpp; 1.5B retained turn-10 context and produced 16/20 valid schema tool actions; invalid actions failed closed |
| M3-04 | PASS | 30 real category-aware turns with WebRTC VAD, policy-routed STT, Qwen2.5-1.5B, and policy-routed Arabic/English Piper voices; category WER and latency reported |
| M3-05 | PASS | 20/20 barge-in cancellation runs; p95 0.105 ms at the software sink boundary; physical driver latency excluded |
| M3-06 | BLOCKED/PARTIAL | Public Egyptian-labelled read speech available; conversational MasriSpeech route returned 404/401 without bypassing access controls |
| M3-07 | PASS FOR STREAM ACCESS | 34 endpoints enumerated; a 250 ms input stream captured 4,000 frames then discarded them, and a silent 3,200-frame output stream opened; subjective quality not measured |
| M3-08 | PASS | Missing model, malformed audio, adapter timeout/error, float WAV, dataset config, and TTS allocation failures actively exercised |
| M3-09 | PASS | Before/after numbers in `M3_BENCHMARK.md` |
| M3-10 | PASS | 19-test regression, compileall, secret scan, diff check, isolation, and corrected 30-turn rerun completed before review |

## Local prototype test matrix (implementation follows review)

| ID | Test | Pass condition |
|---|---|---|
| L1 | Arabic Egyptian scripted turns | All expected intents/transcripts meet the agreed quality threshold |
| L2 | English scripted turns | All expected intents/transcripts meet the agreed quality threshold |
| L3 | Partial STT timing | p95 <= 800 ms |
| L4 | First response audio | p95 <= 1,500 ms |
| L5 | Barge-in | Current TTS is cancelled/ducked within p95 <= 250 ms and listening resumes |
| L6 | Ten-turn context | 10/10 context assertions pass |
| L7 | Tool safety | Denied, malformed, timed-out, and dry-run tools fail closed and are audited without secrets |
| L8 | Failure fallback | Simulated channel failure transitions to text/voice-note mode within 2 s |
| L9 | Reconnect/idempotency | Duplicate and out-of-order events do not duplicate turns or tool effects |
| L10 | Observability | Required redacted timings and state transitions are emitted |
| L11 | Secret scan | No credential/token/API-key pattern in tracked files or history |
| L12 | Existing-system isolation | No files/configs/processes outside this repository are changed |

Evidence for implementation tests must be attached to the milestone PR; this milestone stops at specification.


## Milestone 4 evidence

| ID | Result | Evidence |
|---|---|---|
| M4-01 | PASS | 32 utterances and 64 real incremental faster-whisper prefix inferences; final WER 0.3109 |
| M4-02 | PASS | Selected robust-1200ms endpoint policy: 40 trials, 0 false cuts, decision p95 0.0418 ms; fast/patient comparison remains documented with their stress tradeoffs |
| M4-03 | PASS | 20 streamed Qwen prompts plus 15-turn continuity; system retained and pinned memory recalled |
| M4-04 | PASS | Sentence and phrase Piper strategies, 8 runs each; explicit per-chunk Arabic/English routing |
| M4-05 | PASS/PARTIAL | 50 consecutive sustained local turns completed with 5 interruptions and 3 recoveries; the separate pipelined E2E benchmark completed 40 turns and first-playable p95 was 4,404.22 ms, slower than M3 p95 4,146.59 ms |
| M4-06 | PASS | Three measured experiments: STT beam, LLM threads, and TTS chunk strategy |
| M4-07 | PARTIAL | 10 Egyptian-style and 10 mixed controlled synthetic fixtures; natural corpus still blocked; selected mixed WER 0.7724 |
| M4-08 | PASS | 30/30 interruptions across generation/TTS/sink; zero stale output; cancel p95 0.02 ms |
| M4-09 | PASS | 11 streaming failure/recovery paths actively injected and failed closed |
| M4-10 | PASS | Streaming state/stale-event regression tests added; 28-test suite passes |
| M4-11 | PASS | 10 microphone captures completed and immediately discarded; no ambient audio retained |
| M4-12 | PASS | Required M4 docs and exact raw artifact paths recorded; no provider/billing/credential changes |
