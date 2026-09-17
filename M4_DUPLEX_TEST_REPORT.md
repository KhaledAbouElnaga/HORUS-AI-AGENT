# Milestone 4 Duplex / Barge-in Report

## True overlapping live-device trials

Ten completed trials used concurrent live `sounddevice.InputStream` and `OutputStream` callbacks at the same time on dynamically selected C-Media WASAPI devices. Piper generated real non-zero speech PCM, scaled to 20%, while microphone callbacks received and immediately discarded input frames.

After ten live input callbacks (about 377 ms measured overlap), a deterministic speech-start event was injected into the live input-analysis path. That event cancelled active playback; subsequent output callback frames were zero-filled, the physical stream was stopped, and stale-output counters were measured. Raw microphone audio stayed in callback memory only and was never persisted.

| Metric | Exact result |
|---|---:|
| Overlapping live trials | 10 |
| Trials with non-zero active output | 10/10; 1,759 measured non-zero samples/trial |
| Trials with live microphone callbacks | 10/10; RMS peak 1,510.11–2,628.53 |
| Successful cancellation / no stale output | 10/10 |
| Callback-to-silence p50 / p95 | 0.0177 / 0.0234 ms |
| Physical stream-stop p50 / p95 | 230.1882 / 230.4233 ms |
| Post-cancel non-zero samples | 0 |
| Raw input retained | No |

This is a real overlapping hardware I/O test with active synthesized speech. The speech-start decision is deterministically injected while the microphone callback is active; it is not a claim of validated acoustic echo cancellation or human speech-detection quality. Physical stop p95 meets the 250 ms target narrowly; subjective loudspeaker quality remains **NOT MEASURED**.

The sustained full-pipeline run separately executed five generation/TTS cancellations with zero cancellation failures. The earlier software benchmark executed 30/30 phase-varied cancellations with zero stale output.

Raw evidence: `artifacts/m4_live_duplex_overlap.json` and `artifacts/m4_real_pipeline_50.json`. Reproduce with:

```bash
PYTHONPATH=src python scripts/benchmark_m4_live_duplex.py
```
