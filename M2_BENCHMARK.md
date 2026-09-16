# Milestone 2 Benchmark

Latest isolated local CPU run: 20 turns over all 8 fixture types.

| Measurement | min | median | p95 | max |
|---|---:|---:|---:|---:|
| PCM validation/energy VAD ms | 13.32 | 49.38 | 91.6 | 91.64 |
| STT final ms | 841.54 | 1708.03 | 1787.07 | 1833.73 |
| Agent first output ms | 0.0 | 0.001 | 0.001 | 0.001 |
| TTS first-audio ms | 287.64 | 703.69 | 826.9 | 1163.19 |
| TTS synthesis ms | 287.65 | 703.7 | 826.91 | 1163.2 |
| End-to-end ms | 1603.46 | 2475.41 | 2599.71 | 2746.58 |

- STT model load (cached files, fresh process): 706.42 ms; first download/load observed earlier: 25,406.15 ms.
- Two Piper voices load: 3820.69 ms.
- Mean WER: 0.5311 across 20 turns / 8 fixture types.
- Session continuity: 20 retained turns; 10-turn assertion PASS.
- Process RSS: 473.7 MB; CPU sample: 792.8 percent across logical cores; GPU not used.
- Barge-in software sink: 10/10 cancelled, min 0.04 ms, median 0.064 ms, p95 0.107 ms. Hardware latency NOT MEASURED.

These are local prototype measurements, not production/WhatsApp or conversational-dialect quality claims. TTS first-audio is time until Piper yields its first sentence chunk.
