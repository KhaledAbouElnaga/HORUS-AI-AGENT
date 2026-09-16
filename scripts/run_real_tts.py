"""Run local Piper TTS for Arabic and English fixtures."""
import json
import time
import wave
import tracemalloc
from pathlib import Path
from piper import PiperVoice

ROOT = Path(__file__).parents[1]
OUT = ROOT / 'artifacts' / 'tts'
OUT.mkdir(parents=True, exist_ok=True)
CASES = [
    ('arabic', 'ar_JO-kareem-medium', 'أهلاً يا هورس، عامل إيه النهارده؟'),
    ('english', 'en_US-lessac-medium', 'Hello HORUS, how are you today?'),
]
rows=[]
for label, voice_name, text in CASES:
    voice_path = ROOT / 'artifacts' / 'voices' / f'{voice_name}.onnx'
    tracemalloc.start(); load_start=time.perf_counter(); voice=PiperVoice.load(str(voice_path)); load_ms=(time.perf_counter()-load_start)*1000
    out=OUT/f'{label}.wav'; start=time.perf_counter()
    with wave.open(str(out),'wb') as wav:
        voice.synthesize_wav(text, wav)
    synth_ms=(time.perf_counter()-start)*1000; _,peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
    with wave.open(str(out),'rb') as wav: duration=wav.getnframes()/wav.getframerate()
    rows.append({'language':label,'voice':voice_name,'text':text,'file':str(out.relative_to(ROOT)),'load_ms':round(load_ms,2),'synthesis_ms':round(synth_ms,2),'output_duration_s':round(duration,3),'peak_tracemalloc_kb':round(peak/1024,1),'license':'voice/model metadata in Piper voice repository; verify before redistribution'})
(ROOT/'artifacts/tts_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'voices':len(rows),'output':'artifacts/tts_results.json'},ensure_ascii=False))
