# HORUS AI Agent — Proposed Architecture

## Boundary

Milestone 1 defines interfaces only. Existing HORUS runtime systems are protected and unchanged. No provider, credential, routing, deployment, or WhatsApp account configuration is modified.

## Logical components

```text
Approved channel adapter (future)
  -> call/event normalizer
  -> audio ingress buffer
  -> VAD / turn detector
  -> streaming STT adapter
  -> session + memory policy
  -> agent/reasoning + authorized tools
  -> streaming TTS adapter
  -> interruption controller
  -> audio egress / channel adapter

Fallback channel adapter (text or voice note) uses the same session contract.
Telemetry receives timestamps, state transitions, errors, and redacted IDs only.
```

## Adapter contracts

- `ChannelAdapter`: capability discovery, session lifecycle, inbound events, outbound audio/message, fallback.
- `AudioStream`: bounded frames, timestamps, cancellation, backpressure, codec metadata.
- `SpeechToText`: partial/final hypotheses with confidence and timing.
- `AgentRuntime`: immutable conversation input, tool policy, streamed output events.
- `TextToSpeech`: cancellable audio chunks with first-byte timing.
- `SessionStore`: scoped context, TTL/retention policy, optimistic versioning.
- `ToolExecutor`: allowlist, validation, audit event, timeout, cancellation, dry-run mode.

## Channel decision

The preferred production branch is Meta's official WhatsApp Business Calling API, conditional on account eligibility, review, and verified live-media details.[1][5] A local audio harness is the first implementation boundary. A third-party bridge is not selected until terms, privacy, price, and technical contract are reviewed. Private WhatsApp protocol automation is rejected.

## Reliability

Use bounded queues, cancellation propagation, idempotent event handling, reconnect/backoff, explicit session states, and a deterministic fallback transition. Metrics must include ingress-to-partial-STT, turn-final-to-first-token, response-to-first-audio, barge-in-stop, end-to-end turn, fallback rate, error rate, and dropped/late event counts.

## Sources

[1] https://developers.facebook.com/docs/whatsapp/cloud-api/calling
[5] https://developers.facebook.com/docs/whatsapp/cloud-api/calling/app-review-guidelines
