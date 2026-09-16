# Milestone 3 Benchmark

All values below are observed on this Windows host, CPU-only unless noted. Generated audio, models, and JSON rows remain ignored local artifacts.

## STT comparison

Each configuration ran the same 8 WAV fixtures three times after warm-up: 24 measured transcriptions per configuration.

| Configuration | Mean WER | p50 ms | p95 ms | Load ms | Model cache |
|---|---:|---:|---:|---:|---:|
| faster-whisper tiny/int8/auto/beam1 | 0.5222 | 820.36 | 908.61 | 646.49 | 156,408,143 B |
| faster-whisper base/int8/auto/beam1 | 0.3675 | 1,587.47 | 1,702.49 | 45,010.97 cold download/load | 295,766,789 B |
| faster-whisper base/int8/forced-Arabic/beam5 | **0.3109** | 1,226.07 | 1,594.13 | 617.73 cached load | 295,766,789 B |

The forced-Arabic base configuration is the measured accuracy winner; English remains auto-detected. The fixture set is too small and read-speech biased for a production-quality claim.

## TTS comparison

Seven Arabic, Egyptian, and English phrases were synthesized by each voice.

| Piper voice | First-audio p50 | RTF p50 | Load | Size |
|---|---:|---:|---:|---:|
| ar_JO-kareem-medium baseline | 887.89 ms | 0.217 | 1,649.35 ms | 63,201,294 B |
| ar_JO-kareem-low alternative | 925.72 ms | 0.262 | 3,597.41 ms | 63,201,294 B |

The low voice executed successfully but did not outperform medium. The upstream model card points to a dataset repository instead of stating redistribution terms; legal review remains required before redistribution.

## Local agent comparison

| Model | Load | RSS delta | First-token p50 | Memory turn 10 | Tool evidence |
|---|---:|---:|---:|---|---|
| Qwen2.5-0.5B Instruct Q4_K_M | 300.79 ms | 499.0 MB | 73.23 ms | FAIL | 1/5 simple intents |
| Qwen2.5-1.5B Instruct Q4_K_M | 713.0 ms | 1,662.8 MB | 102.12 ms | **PASS** | 16/20 schema-constrained actions valid; 4 invalid actions failed closed |

Both use llama-cpp-python 0.3.35 on CPU. Qwen2.5 models are Apache-2.0 per the upstream repository. The 1.5B model is the selected experimental local path, not a production default.

## 30-turn real pipeline with selected experimental agent

Pipeline: WebRTC VAD to faster-whisper base/int8 forced-Arabic beam5 to Qwen2.5-1.5B Q4_K_M to Piper kareem-medium.

| Metric | p50 | p95 |
|---|---:|---:|
| VAD | 10.76 ms | 19.93 ms |
| STT | 1,962.96 ms | 2,368.69 ms |
| Agent first token | 1,410.31 ms | 1,648.32 ms |
| TTS first audio | 588.07 ms | 960.37 ms |
| End-to-end | 4,856.86 ms | 5,290.60 ms |

Process loads: STT 743.50 ms, agent 714.16 ms, TTS 1,687.50 ms. Final RSS 2,324.6 MB. RTX 3050 was detected but not used because the installed CTranslate2 and llama.cpp paths were CPU builds.

## VAD, barge-in, and hardware

- WebRTC VAD 2.0.14 classified all 8 speech fixtures as speech and rejected generated silence plus low-level noise.
- 20/20 active software-stream cancellations succeeded: min 0.037 ms, median 0.079 ms, p95 0.105 ms. Physical speaker and driver latency remains excluded.
- sounddevice found 34 endpoints, default input 1 and output 5. A 250 ms input stream opened and captured 4,000 frames, then discarded them; a 3,200-frame silent output stream opened successfully. This verifies device access without retaining ambient audio or producing audible content.

## M2 comparison

| Metric | M2 | M3 selected experimental path |
|---|---:|---:|
| Real turns | 20 | 30 |
| Mean WER | 0.5411 | 0.3109 in repeated STT comparison |
| End-to-end p95 | 2,599.71 ms deterministic agent | 5,290.60 ms Qwen 1.5B agent |
| Barge-in runs | 10 | 20 |
| Agent | deterministic | real local 1.5B, memory PASS, tools 16/20 |
| VAD | energy threshold | frame-based WebRTC VAD |

M3 improves measured STT quality and component realism but materially increases end-to-end latency.
