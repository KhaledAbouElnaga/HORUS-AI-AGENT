# Milestone 3 Test Report

**Scope:** real local voice quality/agent comparison on Windows; no Meta/WhatsApp, provider, credential, or billing changes.

## Executed evidence

| Requirement | Result | Evidence |
|---|---|---|
| 3 real STT configurations | PASS | `scripts/benchmark_stt_configs.py`; 3 configs × 3 repeats × 8 fixtures, 48 warm turns |
| Alternative TTS | PASS | Piper `en_US-amy-low` generated `artifacts/tts/amy_low.wav`; Windows SAPI/pyttsx3 attempt timed out at 300 s and was not selected |
| Real local/free LLM paths | PASS | TinyLlama and Qwen2.5 GGUF via llama.cpp executed; both measured, neither selected due output/tool/memory quality |
| 30 real end-to-end turns | PASS | `scripts/run_real_pipeline.py`; 30 WAV → WebRTC VAD → STT → agent → Piper turns |
| 20 barge-in runs | PASS | `scripts/benchmark_barge_in.py`; all 20 cancelled |
| Improved Egyptian/mixed set | BLOCKED/PARTIAL | Public FLEURS Egyptian-labelled set downloaded; MasriSpeech dataset-server access returned 404/401; mixed fixture is concatenated, not natural code-switch speech |
| Device access | INSPECTED / NOT MEASURED | `sounddevice.query_devices()` found microphone and speakers; no unattended recording/playback performed |
| Failure/recovery | PASS | Config failure, float WAV, TTS allocation, corrupt/missing WAV, adapter timeout/error, missing LLM model, and SAPI timeout actively observed |

## Regression gates

- `17 passed in 0.13s` before the M3 branch work; final run is rerun before delivery.
- `python -m compileall -q src tests scripts`: required.
- Secret scan and `git diff --check`: required.
