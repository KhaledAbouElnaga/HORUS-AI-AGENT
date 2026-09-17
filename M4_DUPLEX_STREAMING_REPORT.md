# Milestone 4 Duplex Streaming Report

## Executed local path

`30 ms PCM frames -> bounded ingress -> WebRTC VAD/endpointing -> genuine 30 ms chunk-fed incremental SST partials + final -> streamed Qwen2.5-1.5B -> incremental Piper phrase synthesis`.

## Stale report cleanup

This report previously referenced superseded candidate artifacts (`artifacts/m4_stt_candidates_checkpoint.json`) and an old 40-turn E2E measurement (`artifacts/m4_streaming_results.json`). The corrective scripts produced:

- `artifacts/m4_stt_candidates_chunked.json` — two 20-turn chunk-fed candidates, 60 partial hypotheses each
- `artifacts/m4_real_pipeline_50.json` — 50 fresh full-pipeline turns with 150 partials

Both are tracked by their artifact manifests; `artifacts/` remains git-ignored.

## STT candidates (corrective)

Two `base/int8` candidates each processed the same 20-turn set as fixed 30 ms chunks. Every turn emitted three deduplicated partial checkpoints before finalization.

| Candidate | Turns / partials | First-partial-after-availability p50 / p95 | Final p50 / p95 | Mean WER | RSS | Drops |
|---|---:|---:|---:|---:|---:|---:|
| cumulative 33/66/90%, beam 1 partial, beam 5 final | 20 / 60 | 1,041.88 / 2,211.84 ms | 1,173.59 / 1,984.23 ms | 0.4455 | 217.42 MB | 0 |
| rolling 3 s at 25/50/75%, beam 5 | 20 / 60 | 1,161.24 / 2,993.46 ms | 1,225.52 / 1,999.93 ms | 0.4455 | 220.59 MB | 0 |

## Endpointing

Selected patient 600 ms policy: 40 trials, 11 false cuts, decision p95 0.02 ms. Applied on every fresh 50-turn sustained stream.

## Agent/TTS duplex behavior

Qwen2.5-1.5B streamed on all 50 sustained turns. The system instruction stayed first; pinned session memory `7319` was recalled at turn 50. Piper synthesized from streamed model text on every turn with phrase chunking and explicit Arabic/English routing. Five interruption turns cancelled generation and TTS emission before stale output could escape.

## Live duplex evidence

Ten concurrent live duplex trials used dynamically selected C-Media WASAPI input/output streams with active 20%-scale Piper speech and live microphone callbacks. Injected speech-start produced callback-silence p95 0.0234 ms and physical stream-stop p95 230.4233 ms; 10/10 trials had non-zero active output (1,759 measured samples each) and zero stale post-cancel samples. No raw microphone audio was retained.

Raw evidence: `artifacts/m4_stt_candidates_chunked.json`, `artifacts/m4_real_pipeline_50.json`, and `artifacts/m4_live_duplex_overlap.json`. Reproduce with:

```bash
PYTHONPATH=src python scripts/benchmark_m4_stt_candidates.py
PYTHONPATH=src python scripts/benchmark_m4_completion.py
PYTHONPATH=src python scripts/benchmark_m4_live_duplex.py
PYTHONPATH=src python scripts/benchmark_m4_failure_recovery.py
```
