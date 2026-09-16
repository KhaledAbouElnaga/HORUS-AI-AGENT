# Lessons

- Keep the first vertical slice event-driven and deterministic; it makes cancellation, ordering, fallback, and metrics testable without a microphone or account.
- Treat out-of-order events as stale and ignore them after recording the metric; replaying them can duplicate agent turns or tool effects.
- Keep tool authorization deterministic and fail closed before adding a real model.
- Record resource numbers with scope and limitations; harness timings are not speech-model latency.
- Time-box local model setup. If a model is unavailable, preserve the adapter contract and continue with the harness.
