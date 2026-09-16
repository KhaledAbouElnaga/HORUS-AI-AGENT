# Milestone 4 Sustained Session Report

## 50-turn session

The local loop completed 50 consecutive turns across Arabic/Egyptian-labelled, MSA, English, and mixed fixtures. It included 5 interruptions, 3 recoverable component restarts, and context recall from the pinned early-session fact through the final turn.

| Metric | Result |
|---|---:|
| Turns | 50 |
| Interruptions | 5 |
| Recoveries | 3 |
| Dropped events | 0 |
| Duplicated events | 0 |
| RSS start / end | 2003.70 / 2065.77 MB |
| RSS growth | 62.07 MB |
| Queue high-water | 0 |
| Agent first-token p95, turns 1–10 / 41–50 | 4428.85 / 2078.88 ms |

The local Qwen runtime produced a Windows access-violation during an earlier long run at turn 20. The final harness catches worker exceptions, emits a safe non-tool fallback, records the recovery, and preserves the session instead of treating the failed model turn as a successful model response.

## Quality boundary

This is a reproducible local streamed session, not a production call-quality or natural-conversation claim. Synthetic Egyptian and code-switch fixtures are documented separately. No raw audio was retained.

Raw rows: `artifacts/m4_completion_results.json` -> `sustained.rows`.
