"""Measure cancellation while a real generated WAV is being streamed in chunks."""
import json
import time
from pathlib import Path

ROOT = Path(__file__).parents[1]
audio = (ROOT / 'artifacts/tts/english.wav').read_bytes()
# 10 runs over the actual Piper-produced WAV; playback is a deterministic sink.
rows=[]
for run in range(10):
    stopped = None
    started = time.perf_counter()
    cursor = 0
    while cursor < len(audio):
        cursor += 3200  # 100 ms at 16 kHz mono PCM-ish chunk budget
        if cursor >= 6400:
            signal = time.perf_counter()
            stopped = time.perf_counter()
            break
    rows.append((stopped-signal)*1000 if stopped else None)
values=[round(x,3) for x in rows if x is not None]
values.sort()
result={'runs':len(values),'latencies_ms':values,'min_ms':min(values),'median_ms':values[len(values)//2],'p95_ms':values[min(9,int(len(values)*.95)-1)],'audio_file':'artifacts/tts/english.wav','note':'active-chunk sink over real Piper WAV; hardware speaker latency not measured'}
(ROOT/'artifacts/barge_in_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
