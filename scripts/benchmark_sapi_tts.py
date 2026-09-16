"""Attempt Windows SAPI through pyttsx3 as an alternative to Piper."""
import json,time
from pathlib import Path
import pyttsx3
ROOT=Path(__file__).parents[1]; out=ROOT/'artifacts/tts'; out.mkdir(parents=True,exist_ok=True)
engine=pyttsx3.init(); voices=engine.getProperty('voices')
rows=[]
for i,voice in enumerate(voices[:4]):
 path=out/f'sapi_{i}.wav'; text='Hello HORUS, this is an offline Windows voice test.'
 start=time.perf_counter(); engine.setProperty('voice',voice.id); engine.save_to_file(text,str(path)); engine.runAndWait(); elapsed=(time.perf_counter()-start)*1000
 rows.append({'index':i,'id':str(voice.id),'name':str(getattr(voice,'name','')),'latency_ms':round(elapsed,2),'file':str(path.relative_to(ROOT)),'bytes':path.stat().st_size if path.exists() else 0})
print(json.dumps({'voices_available':len(voices),'results':rows},ensure_ascii=False))
(ROOT/'artifacts/sapi_tts_results.json').write_text(json.dumps({'voices_available':len(voices),'results':rows},ensure_ascii=False,indent=2),encoding='utf-8')
