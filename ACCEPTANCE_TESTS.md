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
| M4-01 | PASS | Two genuine 30 ms chunk-fed STT candidates, 20 turns each after warm-up; 60 partials per candidate, all turns had multiple deduplicated hypotheses; selected p95 first-partial after availability 2,211.84 ms and final p95 1,984.23 ms |
| M4-02 | PASS | Selected patient-600ms: 11/40 false cuts, decision p95 0.02 ms; the 50-turn rerun applied VAD/endpointing on every fresh chunk stream |
| M4-03 | PASS | Qwen2.5-1.5B streamed on all 50 sustained turns; system retained and pinned value `7319` recalled at turn 50 |
| M4-04 | PASS | Piper synthesized incrementally from streamed model text on all 50 sustained turns; explicit per-chunk Arabic/English routing |
| M4-05 | PASS/PARTIAL | 50 consecutive fresh full-pipeline turns: 150 partials, 5 interruptions, 3 recoveries, 0 drops/duplicates/stale events/cancel failures; latency still misses the M3 baseline |
| M4-06 | PASS | Three measured experiments: STT beam/window policy, LLM threads/model size, and TTS chunk strategy |
| M4-07 | PARTIAL | 10 Egyptian-style and 10 mixed controlled synthetic fixtures; natural corpus still blocked; full-pipeline tiny STT mean WER 0.6321 and synthetic evidence does not establish natural quality |
| M4-08 | PASS | Five full-pipeline cancellations plus 30/30 earlier phase-varied software interruptions; zero stale output/cancel failures |
| M4-09 | PASS | 11 original streaming paths plus focused 9-case failure/recovery runner failed closed |
| M4-10 | PASS | Streaming state/lifecycle/stale-event regression coverage; 31-test suite passes |
| M4-11 | PASS | 10 true overlapping live duplex trials with non-zero Piper output and live microphone callback; injected speech-start stopped output p95 230.4233 ms, callback silence p95 0.0234 ms, 0 stale samples; acoustic speech detection/subjective quality NOT MEASURED |
| M4-12 | PASS | Required M4 reports and exact raw artifact paths recorded; no provider/billing/credential changes |

## Milestone 5 evidence

| ID | Result | Evidence |
|---|---|---|
| M5-01 | PASS | Real HORUS contract discovered in external `D:/HORUS/horus-core/worker/src/index.js`; entrypoints, KV keys, LLM loop, and weather/Wikipedia paths documented |
| M5-02 | PASS | `VoiceRuntimeAdapter` and WAV coordinator delegate session, stream, memory, tools, cancellation, and TTS; no fake default runtime |
| M5-03 | BLOCKED | Worker exposes Telegram-only ingress/egress and no callable local streaming runtime API; known `/health` probe returned HTTP 403 |
| M5-04 | PASS / BLOCKED | Local adapter session isolation and memory/tool seams tested; real three-fact continuity requires blocked transport |
| M5-05 | PASS / BLOCKED | Deny-by-default mutation safety passes locally; three real tool categories and read-only external execution blocked by runtime transport |
| M5-06 | PASS / BLOCKED | Deterministic WAV coordinator exists and live device probe ran; integrated live runtime path blocked (input probe host error, output probe PASS) |
| M5-07 | BLOCKED | Required 50-turn/15-minute real integrated run cannot execute without callable HORUS transport |
| M5-08 | PASS / NOT MEASURED | Local failure/recovery seams tested; integrated runtime failure matrix and required M5 latency/RSS drift not measured |
| M5-09 | PASS | Full local regression and compile checks pass; tracked-file secret scan and diff check recorded in PR evidence |
| M5-10 | BLOCKED | M5 reports are complete with exact PASS/PARTIAL/BLOCKED/NOT MEASURED states; external runtime integration remains the gate |
