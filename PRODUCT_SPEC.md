# HORUS AI Agent — Product Specification (Milestone 1)

## Product outcome

HORUS should support a natural, realtime, two-way voice conversation with the owner through an approved WhatsApp business calling path when that path is available. Arabic-first means natural Egyptian Arabic is the primary quality target; English is the secondary supported language.

## In scope for the future product

- Realtime speech input/output.
- Turn detection and interruption/barge-in.
- Context maintained across a call/session.
- Tool-capable reasoning with explicit tool permissions.
- Observable latency, errors, and fallback transitions.
- Text and voice-note fallback when realtime calling is unavailable.

## Out of scope for Milestone 1

Product implementation, Meta onboarding, account changes, billing, paid providers, production traffic, recording/transcription activation, and changes to existing HORUS systems/providers/credentials/routing.

## Measurable targets for the first local prototype

Targets are engineering acceptance goals, not claims about WhatsApp performance:

- VAD end-of-turn decision: p95 <= 300 ms after configured silence.
- First partial STT result: p95 <= 800 ms from audio availability.
- Agent first-token event: p95 <= 1,200 ms after finalized user turn in the local harness.
- First audible TTS audio: p95 <= 1,500 ms after agent response begins.
- Barge-in stop/duck command: p95 <= 250 ms after interruption detection.
- Session continuity: 100% of scripted context checks pass across a 10-turn test session.
- Fallback decision: <= 2 s after a simulated realtime-channel failure.
- No secret leakage in logs, artifacts, or Git history.

## Quality and safety requirements

The system must disclose uncertainty, avoid silently executing high-impact tools, preserve user control, and fail closed when channel authorization or tool authorization is absent. Audio and transcript retention must be configurable and off by default for prototypes.

## Fallback UX

If WhatsApp realtime calling is not eligible or fails: acknowledge in text, accept a voice note or text turn, process it through the same session contract, and reply with a voice note/text response. The fallback must not pretend that a live call exists.
