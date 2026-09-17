# M5 Memory and Session Report

## Real local HORUS path

`LocalHorusPythonPort` delegates to `D:/HORUS/horus-core/app/adapters/memory/store.py`. The store is an in-memory local fallback in this installation; it is not production KV/Supabase persistence. The adapter namespaces keys by session ID and filters reads by that namespace.

## Executed evidence

Command: `PYTHONPATH=src python scripts/run_m5_local_runtime_evidence.py`

Result: two real adapter sessions; three facts (`name`, `city`, `role`) introduced; `city=Cairo` corrected to `city=Giza`; late lookup returned `Giza`; second session returned no city; `forget` removed the city fact. All are calls to the installed HORUS memory module, not a test double.

- Three facts introduced/recalled late: **PASS**
- Correction/update: **PASS**
- Forget: **PASS** (the local store supports `forget`; Worker `/forget` separately clears context)
- Two-session isolation: **PASS** for the adapter namespace over the local store
- Production Worker KV continuity: **NOT MEASURED**; its `ctx:<user-id>` and `facts:<user-id>` path requires its Telegram/Worker transport

No persistent external memory was changed.