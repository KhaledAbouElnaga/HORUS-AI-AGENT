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

## Corrected 30-turn real pipeline with selected experimental agent

Pipeline: WebRTC VAD to category-aware faster-whisper base/int8 beam5 to Qwen2.5-1.5B Q4_K_M to category-aware Piper. English STT uses auto-detection; Egyptian Arabic, MSA, and the Arabic-led synthetic mixed fixture use forced Arabic. English replies use `en_US-lessac-medium`; Arabic replies use `ar_JO-kareem-medium`. Mixed replies use the voice matching their dominant output script, with Arabic as the tie-break. The system instruction is retained separately from the rolling eight-message conversational window.

| Metric | p50 | p95 |
|---|---:|---:|
| VAD | 10.76 ms | 20.55 ms |
| STT | 2,201.63 ms | 2,663.54 ms |
| Agent first token | 800.31 ms | 1,015.62 ms |
| TTS first audio | 176.87 ms | 345.92 ms |
| End-to-end | 3,249.78 ms | 4,146.59 ms |

| Category | Turns | Mean WER | STT p50 / p95 | E2E p50 / p95 | STT route | TTS voice observed |
|---|---:|---:|---:|---:|---|---|
| Egyptian Arabic | 12 | 0.3972 | 2,327.90 / 2,397.54 ms | 3,549.79 / 3,714.52 ms | forced Arabic | kareem-medium 12/12 |
| MSA Arabic | 8 | 0.1667 | 2,082.92 / 2,227.49 ms | 3,120.51 / 3,266.52 ms | forced Arabic | kareem-medium 8/8 |
| English | 7 | 0.0726 | 2,626.71 / 2,666.66 ms | 4,114.13 / 4,193.80 ms | auto-detect | lessac-medium 7/7 |
| Mixed synthetic | 3 | 0.8125 | 1,511.46 / 1,519.30 ms | 2,562.50 / 2,614.30 ms | forced Arabic | kareem-medium 3/3 |

Overall E2E mean WER was 0.3015. Process cold loads were STT 745.34 ms, agent 739.66 ms, Arabic TTS 1,850.64 ms, and English TTS 3,206.57 ms; final RSS was 2,267.9 MB. The English route no longer forces Arabic or synthesizes English through an Arabic voice. The natural code-switch limitation remains: the mixed sample is concatenated, Arabic-led, and has high WER, so it cannot support a production code-switch claim.

## VAD, barge-in, and hardware

- WebRTC VAD 2.0.14 classified all 8 speech fixtures as speech and rejected generated silence plus low-level noise.
- 20/20 active software-stream cancellations succeeded: min 0.037 ms, median 0.079 ms, p95 0.105 ms. Physical speaker and driver latency remains excluded.
- sounddevice found 34 endpoints, default input 1 and output 5. A 250 ms input stream opened and captured 4,000 frames, then discarded them; a 3,200-frame silent output stream opened successfully. This verifies device access without retaining ambient audio or producing audible content.

## M2 comparison

| Metric | M2 | M3 selected experimental path |
|---|---:|---:|
| Real turns | 20 | 30 |
| Mean WER | 0.5411 | 0.3109 in repeated STT comparison |
| End-to-end p95 | 2,599.71 ms deterministic agent | 4,146.59 ms corrected policy-routed Qwen 1.5B agent |
| Barge-in runs | 10 | 20 |
| Agent | deterministic | real local 1.5B, memory PASS, tools 16/20 |
| VAD | energy threshold | frame-based WebRTC VAD |

M3 improves measured STT quality and component realism but materially increases end-to-end latency.
