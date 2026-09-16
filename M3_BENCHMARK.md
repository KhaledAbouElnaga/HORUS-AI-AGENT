# Milestone 3 Benchmark

## STT configuration comparison

All configurations used the same 8 PCM WAV fixtures and 3 repeats; warm summary uses the 16 non-first-load runs per configuration.

| Configuration | Mean WER | p50 STT ms | p95 STT ms | Load ms | Max RSS MB |
|---|---:|---:|---:|---:|---:|
| faster-whisper tiny/int8/auto | 0.5222 | 617.15 | 719.12 | 885.04 | 182.2 |
| faster-whisper tiny/int8/forced language | 0.5300 | 369.58 | 2220.54 | 426.15 | 206.6 |
| faster-whisper base/int8/auto | **0.3675** | 1213.23 | 1435.77 | 577.56 | 267.3 |

The preferred accuracy path is `base/int8/auto`; tiny remains the latency/resource fallback.

## TTS comparison

| Path | Result |
|---|---|
| Piper `ar_JO-kareem-medium` | Arabic WAV generated; baseline measured in M2 |
| Piper `en_US-lessac-medium` | English WAV generated; baseline measured in M2 |
| Piper `en_US-amy-low` | **PASS**; WAV generated, 125.85 ms synthesis, 116,780 bytes |
| Windows SAPI via pyttsx3 | **BLOCKED**; attempted and timed out after 300 s in unattended environment |

## Local LLM comparison

| Path | Result |
|---|---|
| TinyLlama 1.1B Q4_K_M / llama.cpp | Executed: 3 prompts, 636.58 ms load, 1124.7 MB RSS; Arabic/instruction outputs were poor |
| Qwen2.5 0.5B Instruct Q4_K_M / llama.cpp | Executed: 15 Arabic/English/mixed/memory/tool prompts, 303.76 ms load, 497.5 MB RSS delta, 67.63 ms median first token; memory recall failed and 1/5 tool intents matched |

Neither local LLM is selected as the production agent. The deterministic agent remains the safe default until a reviewed quality/tool-policy milestone.

## M3 end-to-end

30 real turns, 8 fixture types, CPU-only, TinyLlama not used in the selected timing path:

- VAD p95: **44.33 ms**
- STT p95: **1030.28 ms**
- Agent first output p95: **0.001 ms** deterministic adapter
- TTS first audio p95: **467.71 ms**
- End-to-end p95: **1400.71 ms**
- Model load: 843.86 ms warm cache
- Piper voice load: 3249.95 ms
- RSS: 517.7 MB
- Context: 30 turns; 10-turn continuity assertion PASS

## Barge-in

20/20 active software-stream cancellations succeeded. Min/median/p95 cancellation-to-stop: **0.033 / 0.060 / 0.143 ms**. This excludes physical speaker and driver latency.

## Before/after Milestone 2

| Metric | M2 baseline | M3 | Interpretation |
|---|---:|---:|---|
| Real turns | 20 | **30** | M3 meets the expanded run count |
| STT p95 | 1075.13 ms | **1030.28 ms** | Different run/configuration; modest improvement |
| End-to-end p95 | 1428.56 ms | **1400.71 ms** | Different run/configuration; modest improvement |
| Barge-in runs | 10 | **20** | M3 doubles coverage |
| STT quality | mean WER 0.5411 | **0.3675 base warm comparison** | Base model improves accuracy at higher latency |
| VAD | energy gate | **WebRTC VAD p95 44.33 ms** | More realistic frame-based gate |

These are local CPU measurements, not production or microphone performance claims.
