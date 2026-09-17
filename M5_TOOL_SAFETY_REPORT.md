# M5 Tool Safety Report

## Real categories exercised

`LocalHorusPythonPort.invoke_tool()` delegates to the installed HORUS `app.core.agent.handle_text()` command path. Command: `PYTHONPATH=src python scripts/run_m5_local_runtime_evidence.py`.

The following real read-only/local categories executed successfully: `status` (`/status`), `tasks` (`/tasks`), and `cost` (`/cost`). The result recorded `tools: ["cost", "status", "tasks"]`, with no task mutation.

The Worker source additionally contains `liveWeather()`/Open-Meteo and `liveWiki()`/Arabic Wikipedia. Those read-only external categories were source-verified but not executed because the Worker transport is Telegram-only and an authorized exchange would require protected credentials/egress. They are **NOT MEASURED**, not claimed as exercised.

## Safety

- Mutation/destructive categories: **PASS** — `DenyByDefaultSafety` denies unregistered categories before runtime delegation; local test attempted `delete` and received `PermissionError`.
- Malformed/timeout/tool exception: **PASS** at adapter contract; **NOT MEASURED** through a real tool execution.
- Cancellation during/after tool result: **PARTIAL** — generation stale rejection is tested, but the installed Python agent has no native cancellable stream.
- No destructive action, external message, billing, provider, credential, or deployment change was performed.