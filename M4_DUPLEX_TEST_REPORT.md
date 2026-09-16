# Milestone 4 Duplex / Barge-in Report

## Executed evidence

- Software full-duplex path: 30 local interruption trials spanning generation, TTS synthesis, and software sink cancellation.
- Device-level full-duplex path: 10 trials using the default Windows input/output streams. Captures were held in memory and discarded immediately; no ambient audio was written.
- Software cancellation: p95 0.02 ms in the streaming benchmark; stale output was suppressed in all trials.
- Physical output stop: p50 56.01 ms, p95 63.57 ms, 0 stale resumptions, 0 failures.
- Input listening remains active while the software output path is active. A speech-start cancellation advances a monotonic epoch and invalidates generation, queued synthesis, and sink emission.

## Boundary

The device measurement used silent output frames for unattended safety. It proves simultaneous input/output stream access and stop propagation, not acoustic echo performance, audible loudspeaker stop time, or subjective quality. Meta/WhatsApp integration was not used.

Raw evidence: `artifacts/m4_completion_results.json` and `artifacts/m4_streaming_results.json` (ignored generated artifacts).
