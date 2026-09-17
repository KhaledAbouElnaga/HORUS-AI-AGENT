# M5 Memory and Session Report

## Real path and execution

`LocalHorusPythonPort` delegates to `D:/HORUS/horus-core/app/adapters/memory/store.py`. This installed local store is the app's documented in-memory fallback; production Worker KV (`facts:<user-id>` and `ctx:<user-id>`) remains separate and was not mutated.

`PYTHONPATH=src python scripts/run_m5_sustained_local.py` fed real Piper-generated spoken memory phrases through faster-whisper, then through `LocalHorusPythonPort` and the installed memory store. No transcript was injected.

## Evidence

- Three facts introduced early: name, location, country (the final STT text is preserved in `artifacts/m5_sustained_local.json`).
- One correction: the same location key was written again from Cairo to the final recognized value `keys`.
- Late recall: session `m5-sustained-a` returned the corrected location value `keys`.
- Two-session isolation: session `m5-sustained-b` returned no location row; `memory_cross_session_isolation: true`.
- Forget behavior: the real store's `forget()` path is covered by local runtime tests; the sustained run exercised correction/override rather than deleting the late-recalled fact.

Memory-through-voice: **PASS for local in-memory HORUS store and two-session adapter scope**. Production Worker KV continuity: **NOT MEASURED**.