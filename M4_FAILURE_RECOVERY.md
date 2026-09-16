# M4 Failure and Recovery

## Executed failures

The primary benchmark actively injected 11 cases and failed closed in all 11:

1. STT worker exception
2. stalled partial stream timeout
3. VAD false endpoint
4. LLM cancellation
5. TTS chunk failure
6. audio queue backpressure
7. duplicate chunk
8. out-of-order chunk
9. missing voice
10. oversized context truncation
11. low-memory safeguard

The sustained session additionally recovered the STT, agent, and TTS components at turns 12, 28, and 44 and then continued to turn 50 without duplicate turns or stale output. A 50-frame overload trial proved the 8-frame queue drops excess input explicitly and drains cleanly.

## Security/isolation

- Tool-like intents: 5/5 denied; no tool side effect occurred.
- No credentials or paid endpoints were introduced.
- No Meta/WhatsApp, provider, routing, billing, or unrelated runtime configuration changed.
- Ambient microphone samples from 10 capture and 10 live barge-in trials were discarded and never written to disk.
- Cancellation epochs and event sequence ledgers reject stale or duplicated output.

## Remaining limits

- Natural licensed Egyptian/code-switch conversational data is still BLOCKED; controlled substitutes remain clearly labelled.
- Selected endpoint correctness requires a 1200 ms tail, above the 900 ms target.
- Sustained late-session first-token p95 regressed to 4459.37 ms.
- Subjective audible output quality is NOT MEASURED.
