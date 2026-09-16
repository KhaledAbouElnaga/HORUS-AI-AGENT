# M4 Sustained Run

A single local session completed **50 consecutive turns** using measured real STT outputs, a real streaming Qwen2.5-1.5B agent, and real Piper synthesis. It included 5 interruption turns and 3 explicit component recoveries.

| Metric | Result |
|---|---:|
| Turns | 50/50 |
| Interruptions | 5 |
| Recoveries | 3 |
| RSS start / end | 2004.56 / 2067.26 MB |
| Agent first-token p95, first 10 | 2942.89 ms |
| Agent first-token p95, last 10 | 4459.37 ms |
| Duplicate events | 0 |
| Dropped events in normal session | 0 |
| Errors | 0 |

The first-token degradation is measurable and means the latency target is **not met** late in the run. The session remains bounded by `[system] + latest 8 messages`; pinned session memory preserves the required fact.

A separate queue overload trial offered 50 timestamped frames to an 8-frame queue: 8 accepted, 42 explicitly dropped, high-water 8, all 8 accepted frames drained, and final depth 0. This validates bounded backpressure rather than allowing hidden memory growth.

Live-device barge-in ran 10 trials while a real Windows output stream was active and microphone input supplied the interruption signal. Audio was immediately discarded. Physical stream stop p50 was **66.01 ms**, p95 **144.04 ms**, with 0 stale resumes. The separate software pipeline completed 30/30 phase-varied cancellations with 0 stale text/audio.

Physical loudspeaker acoustics and subjective quality remain NOT MEASURED; output frames were silent to avoid unattended audible playback.
