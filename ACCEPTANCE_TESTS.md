# Milestone 1 Acceptance Tests

## Research/specification gates

- [ ] M1-R1: Research document distinguishes official, private/unsupported, third-party, and local-only paths.
- [ ] M1-R2: Every externally sourced WhatsApp claim has a source URL and access date.
- [ ] M1-R3: Account/region eligibility, approval, SIP/media, policy, and cost unknowns are listed as gates rather than guessed.
- [ ] M1-R4: No Meta account, billing, credential, or existing HORUS runtime change occurred.

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
