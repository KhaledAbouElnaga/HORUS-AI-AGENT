# Milestone 4 Streaming Architecture

## Executed local path

`30 ms PCM frames -> WebRTC VAD endpointing -> incremental faster-whisper prefixes -> final beam-5 transcript -> streamed Qwen2.5-1.5B tokens -> phrase/sentence chunker -> language-routed Piper -> cancellable software audio sink`

The implementation is in `src/horus_local_voice/streaming.py`. `WavChunkIngress` and `MicrophoneIngress` emit timestamped fixed frames; `BoundedAudioIngress` applies explicit backpressure; `StreamSession` owns lifecycle and recovery. `IncrementalTranscriber` exposes partial/final observations; `detect_endpoint` evaluates frame policies; `PipelinedResponder` starts TTS before model completion; `CancellationEpoch` invalidates generation, queued TTS, and sink output atomically; `StreamState` rejects duplicate and stale sequence numbers. The system instruction is always prepended outside the bounded recent-message window. A pinned session-memory fact is also outside that rolling window.

## State and cancellation

Each response receives a monotonic epoch. Barge-in sets its cancellation event and advances the epoch. Model deltas, synthesized chunks, and sink writes check the epoch immediately before emission. Output from an old epoch cannot resume. Thirty live local-model interruption runs covered generation, TTS synthesis, and software-sink phases with zero stale emissions.

## Routing

- English input: STT auto detection; English-dominant TTS chunks use `en_US-lessac-medium`.
- Egyptian/MSA and Arabic-led mixed input: forced Arabic final STT; Arabic-dominant TTS chunks use `ar_JO-kareem-medium`.
- Mixed output is routed per chunk by dominant Unicode script, Arabic on ties.
- Streaming partials may use beam 1 for latency, but the accepted final transcript remains beam 5 because the measured four-file comparison traded mean WER 0.3500 for 0.4222 at beam 1.

## Isolation and limits

This is CPU-only, local, and free. Core benchmark paths use files/software sinks; 10 separate device-level duplex interruption trials opened the default Windows input and output streams and discarded captures immediately. It does not alter Meta/WhatsApp, HORUS runtime providers, credentials, routing, billing, or paid services. Generated fixtures and raw JSON remain ignored under `artifacts/`. No ambient audio was retained. Results are Windows-host measurements, not production SLOs.

## Reproduction

```bash
PYTHONPATH=src python scripts/generate_m4_language_fixtures.py
PYTHONPATH=src python scripts/benchmark_m4_streaming.py
PYTHONPATH=src python scripts/benchmark_m4_stt_candidates.py
PYTHONPATH=src python scripts/benchmark_m4_completion.py
PYTHONPATH=src python scripts/benchmark_m4_failure_recovery.py
PYTHONPATH=src python -m pytest -q
```
