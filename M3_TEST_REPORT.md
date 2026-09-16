# Milestone 3 Test Report

Scope: Issue #7 only. No Meta or WhatsApp, existing HORUS runtime/provider, credential, routing, billing, or paid-service changes.

| Requirement | Result | Executed evidence |
|---|---|---|
| Three STT configurations | PASS | 72 measured transcriptions plus warm-ups on one 8-file set; exact WER, latency, and resource rows in local JSON |
| Alternative TTS | PASS | Piper kareem-low and medium each synthesized seven phrases; low did not outperform baseline |
| Real local/free LLM | PASS/PARTIAL | Qwen 0.5B and 1.5B ran locally; 1.5B passed turn-10 recall and 16/20 schema tool choices; four invalid choices failed closed |
| 30 real E2E turns | PASS | Corrected category-aware real WAV, VAD, STT, Qwen, and TTS pipeline completed 30 turns; exact category metrics are in M3_BENCHMARK.md |
| 20 barge-in runs | PASS | 20/20 software-stream cancellation; physical driver latency excluded |
| Egyptian/mixed data | BLOCKED/PARTIAL | Current Egyptian-labelled set is read speech; natural code-switch fixture unavailable; public candidates lacked usable raw audio/transcripts or stated license |
| Live devices | PASS for stream access | Input captured 250 ms and discarded; output played silence; no subjective microphone or speaker quality claim |
| Failure/recovery | PASS/PARTIAL | Missing/corrupt audio, adapter timeout/error, missing model and invalid tool outputs executed; invalid tools fail closed |
| Before/after | PASS | M2 comparison in M3_BENCHMARK.md |

## Review corrections verified

- English input now uses STT auto-detection and `en_US-lessac-medium` TTS; Arabic categories retain forced-Arabic STT and kareem-medium TTS.
- Mixed input policy is explicit: the synthetic Arabic-led fixture uses forced-Arabic STT; output TTS follows dominant reply script with an Arabic tie-break.
- The system instruction is always prepended outside the rolling eight-message history. A regression test executes 12 turns and verifies retention.
- The rerun reports WER and component/end-to-end latency independently for Egyptian Arabic, MSA, English, and mixed categories.
- 19 automated tests pass after the corrections.

## Reproduction

1. python scripts/download_fixtures.py
2. PYTHONPATH=src python scripts/benchmark_m3_stt.py
3. python scripts/benchmark_m3_tts.py
4. python scripts/benchmark_m3_agent.py
5. python scripts/benchmark_m3_agent_1_5b.py
6. python scripts/benchmark_m3_tools.py
7. PYTHONPATH=src python scripts/benchmark_m3_e2e.py
8. PYTHONPATH=src python scripts/benchmark_barge_in.py
9. PYTHONPATH=src python scripts/benchmark_vad.py
10. python scripts/probe_audio_devices.py

Model downloads are intentionally not committed. See requirements-m3-local.txt and model URLs in M3_EVALUATION_DATA.md.
