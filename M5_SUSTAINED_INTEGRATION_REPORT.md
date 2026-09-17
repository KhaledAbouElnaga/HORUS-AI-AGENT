# M5 Sustained Integration Report

## Executed real local run

Command: `PYTHONPATH=src python scripts/run_m5_sustained_local.py`

The run decoded every input WAV with the real faster-whisper `tiny/int8` path, passed the resulting transcript to the installed HORUS Python core, invoked real command/memory paths, synthesized each response with Piper, and discarded audio after counting chunks. No cached transcript rows were used.

| Requirement | Result |
|---|---|
| Consecutive integrated turns | **PASS — 50/50** |
| Real sessions | **PASS — `m5-sustained-a`, `m5-sustained-b`** |
| Real tool-mediated turns | **PASS — 45** across status/tasks/cost |
| Arabic / English input turns | **PASS — 20 / 30** |
| Mixed-language input | **PASS as concatenated Arabic+English WAV input; NOT MEASURED as bilingual decoded text** |
| Interruptions/cancellation calls | **PASS — 5; stale audio after cancel: 0** |
| Memory early introduction/correction/late recall | **PASS** |
| Queue/drop/duplicate metrics | **PARTIAL — coordinator path ran; no drops/duplicates observed; no independent queue stress in this run** |
| RSS drift | **PASS — 502.98 → 732.59 MB, +229.61 MB** |
| Runtime response-ready p95 | **21.027 ms** |
| Response-ready → first audio p95 | **213.577 ms** |
| User-end → first audio p95 | **3,553.642 ms** |
| Tool intent → tool result p95 | **11.46 ms** |

## Recovery events

Three active recovery injections were executed in the same local runtime path (turns 12/24/36): memory read failure → real retry; tool timeout → real retry; Piper TTS failure → discard and retry. Each recovered with stale output 0. Full matrix: `artifacts/m5_failure_matrix.json`; event artifact: `artifacts/m5_recovery_events.json`.

Artifact: `artifacts/m5_sustained_local.json` (ignored generated evidence). Native first-token latency is **NOT MEASURED** because the installed HORUS agent returns complete responses.

## Boundary

This is real local HORUS execution, not completion of the deployed Telegram Worker integration. Native runtime streaming, mid-generation cancellation, provider-backed arbitrary conversation, and production KV are separate **PARTIAL / NOT MEASURED** gates.