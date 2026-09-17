# Milestone 4 Language Quality

## Evidence boundary

The M3 public-data search boundary remains: candidate Egyptian/code-switch datasets either lacked reusable raw audio/transcripts or a stated license, or returned datasets-server 404/401. No gated source, credential, or unclear-license corpus was imported.

To expand reproducible coverage without making a natural-speech claim, `scripts/generate_m4_language_fixtures.py` generated 10 Egyptian-style Arabic read-speech substitutes and 10 mixed substitutes. Mixed files concatenate local Arabic and English Piper segments with an 80 ms gap. This is controlled synthetic evidence, not spontaneous Egyptian or natural code-switch audio.

## Measured route comparison

| Set | Route | Utterances | Mean WER | Latency p50 / p95 |
|---|---|---:|---:|---:|
| Egyptian synthetic | auto | 10 | 0.3648 | 1,581.63 / 2,707.71 ms |
| Egyptian synthetic | forced Arabic | 10 | 0.3648 | 849.97 / 897.99 ms |
| Mixed synthetic | auto | 10 | 0.8057 | 1,499.33 / 3,198.10 ms |
| Mixed synthetic | forced Arabic | 10 | 0.7724 | 819.29 / 2,294.51 ms |

Forced Arabic is selected for Arabic-led mixed input on this evidence. It slightly improved synthetic mixed WER from 0.8057 to 0.7724 and materially reduced latency. M3 mixed WER was 0.8125, so the controlled result improved by 0.0401 absolute, but remains poor and is not proof of natural code-switch robustness. English remains auto-detected. TTS routes each output chunk by dominant script.

Raw manifest: `artifacts/m4_language_manifest.json`. Raw measurements: `artifacts/m4_streaming_results.json` -> `language_quality`.
