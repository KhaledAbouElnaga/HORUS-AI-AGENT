# Milestone 4 Duplex / Barge-in Report

## Executed evidence

- Software full-duplex path: 30 local interruption trials spanning generation, TTS synthesis, and software sink cancellation.
- Physical device path: 10 trials using the default Windows input/output streams. Captures were held in memory and discarded immediately; no ambient audio was written.
- Software cancellation: p95 0.02 ms in the streaming benchmark; stale output was suppressed in all trials.
- Physical output stop: p50 56.01 ms, p95 63.57 ms, 0 stale resumptions, 0 failures.
- Input listening remains active while the software output path is active. A speech-start cancellation advances a monotonic epoch and invalidates generation, queued synthesis, and sink emission.

## Boundary

The physical measurement is a device open/read/write smoke and stop-latency measurement, not a subjective microphone or speaker quality assessment. Meta/WhatsApp integration was not used.

Raw evidence: `artifacts/m4_completion_results.json` and `artifacts/m4_streaming_results.json` (ignored generated artifacts).
