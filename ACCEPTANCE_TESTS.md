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
| M2-08 | NOT YET MEASURED | Real STT/TTS, microphone, and dialect quality; no model installed |
| M2-09 | BLOCKED | Meta/WhatsApp integration intentionally deferred |

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
