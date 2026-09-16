# M4 Duplex Streaming Report

## Ingress and state machine

`src/horus_local_voice/streaming.py` now provides timestamped `AudioChunk` objects, WAV replay and microphone ingress adapters, a bounded queue with explicit drop/backpressure accounting, session lifecycle/recovery, incremental STT results, endpointing, epoch-based cancellation, stale-event rejection, text chunking, script-aware voice routing, and a pipelined responder.

## Two real STT candidates

Both candidates ran 20 audio turns on CPU/int8 after warm-up. The same set included Egyptian-labelled, MSA, English, mixed, and controlled substitutes.

| Candidate | Partial p50 / p95 ms | Final p50 / p95 ms | mean WER | RSS MB |
|---|---:|---:|---:|---:|
| rolling prefix 50%, beam 1 | 1556.99 / 4391.71 | 1406.34 / 2824.28 | 0.5231 | 247.7 |
| 3-second window at 75%, beam 5 | 2167.36 / 3852.81 | 2280.97 / 3921.80 | 0.4432 | 244.9 |

The beam-1 rolling candidate is selected for latency. Partials are revisions, not duplicated append-only text; raw rows retain every hypothesis.

## Endpointing

The original 300 ms and 600 ms policies each ran 40 trials. Stress pauses produced 25/40 and 11/40 early cuts. A selected 1200 ms robust policy then ran 40 trials with **0 early cuts**, trading another 600–900 ms of endpoint tail for correctness. This deliberately misses the 900 ms speech-end target and is reported as a measured tradeoff, not hidden.

## Agent/TTS duplex behavior

Qwen2.5-1.5B streamed 20 category-balanced prompts in the primary run and a separate 15-turn continuity session. The system instruction stayed first and pinned-memory recall passed on every continuity turn. Five tool-like intents executed through the real model and were denied before any side effect. Piper sentence/phrase chunking starts before full model completion and routes each chunk by script.

Commands:
```bash
PYTHONPATH=src python scripts/benchmark_m4_stt_candidates.py
PYTHONPATH=src python scripts/benchmark_m4_streaming.py
PYTHONPATH=src python scripts/benchmark_m4_endpoint_selected.py
PYTHONPATH=src python scripts/benchmark_m4_completion.py
```

Raw outputs: `artifacts/m4_stt_candidates_checkpoint.json`, `artifacts/m4_streaming_results.json`, `artifacts/m4_endpoint_selected.json`, and `artifacts/m4_completion_results.json`.
