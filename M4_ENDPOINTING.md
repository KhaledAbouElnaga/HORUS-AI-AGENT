# Milestone 4 Endpointing

WebRTC VAD aggressiveness 2 processed 30 ms frames. Forty trials per policy included normal files, injected 360 ms mid-utterance pauses, and silence-only inputs. Piper 22.05 kHz fixtures were resampled in memory to 16 kHz only for WebRTC VAD.

| Policy | End silence | False cuts | Silence false starts | Tail p50 / p95 | Decision p95 |
|---|---:|---:|---:|---:|---:|
| fast | 300 ms | 17/40 | 0/4 | 0 / 300 ms | 0.03 ms |
| patient | 600 ms | 11/40 | 0/4 | 0 / 270 ms observed | 0.02 ms |

The patient policy is the measured default, but 11 false cuts remain. Internal read-speech pauses and the synthetic pause injection make the 300 ms policy unsuitable. The observed tail metric can be below the configured silence window when a file ends naturally; it is not a claim of a 270 ms configured endpoint. A production loop should reopen a turn if post-final speech appears.

Raw rows: `artifacts/m4_streaming_results.json` -> `endpointing.rows`.
