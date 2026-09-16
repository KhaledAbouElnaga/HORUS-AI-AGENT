# Lessons

- Downloading public FLEURS fixtures can fail when a dataset config is wrong; query the dataset-server config and preserve the exact manifest.
- Normalize downloaded audio to mono 16 kHz PCM before using Python's `wave` module; FLEURS returned float WAV that the stdlib reader rejected.
- Bound text sent to local TTS; an unbounded Arabic transcript caused ONNX Runtime `bad allocation`, so the prototype records the failure and keeps the deterministic path alive.
- Treat out-of-order events as stale and ignore them after recording the metric; replaying them can duplicate agent turns or tool effects.
- Keep tool authorization deterministic and fail closed before adding a real model.
- Record resource numbers with scope and limitations; harness timings are not speech-model latency.
- Time-box local model setup. If a model is unavailable, preserve the adapter contract and continue with the harness.
- Compare model configurations on identical fixtures and repeated warm runs; a lower-latency forced-language path can have a severe p95 outlier.
- Treat model quality and runtime as separate gates: TinyLlama executed locally but produced unusable Arabic/instruction outputs, so it is not the selected agent path.
- Keep physical device tests separate from unattended file tests; enumerating a microphone is not evidence that recording/playback quality passed.
