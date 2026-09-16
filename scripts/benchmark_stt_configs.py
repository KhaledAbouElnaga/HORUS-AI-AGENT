"""Benchmark three real faster-whisper configurations on the identical local fixture set."""
import json, statistics, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
import psutil
from faster_whisper import WhisperModel
from horus_local_voice.real_audio import nearest_rank, word_error_rate

ROOT=Path(__file__).parents[1]; proc=psutil.Process(); manifest=json.loads((ROOT/'artifacts/audio_manifest.json').read_text(encoding='utf-8'))
def norm(value): return value.replace(chr(92), '/')
by_file={norm(item['file']):item for item in manifest if 'expected' in item}
for item in manifest:
 if 'expected' not in item: item['expected']=' '.join(by_file[norm(name)]['expected'] for name in item['composed_from'])
configs=[
 {'name':'tiny-int8-auto','model':'tiny','compute':'int8','force_language':False},
 {'name':'tiny-int8-forced-language','model':'tiny','compute':'int8','force_language':True},
 {'name':'base-int8-auto','model':'base','compute':'int8','force_language':False},
]
rows=[]; summary=[]
for cfg in configs:
 load=time.perf_counter(); model=WhisperModel(cfg['model'],device='cpu',compute_type=cfg['compute']); load_ms=(time.perf_counter()-load)*1000
 for repeat in range(3):
  for item in manifest:
   path=ROOT/item['file']; forced=None
   if cfg['force_language']: forced='ar' if item.get('language') in ('Arabic','ar') else 'en'
   start=time.perf_counter(); seg,info=model.transcribe(str(path),beam_size=1,vad_filter=False,language=forced); text=' '.join(s.text.strip() for s in seg).strip(); latency=(time.perf_counter()-start)*1000
   rows.append({'config':cfg['name'],'repeat':repeat+1,'file':item['file'],'latency_ms':round(latency,2),'wer':round(word_error_rate(item['expected'],text),4),'detected_language':info.language,'forced_language':forced,'observed':text,'rss_mb':round(proc.memory_info().rss/1024/1024,1)})
 subset=[r for r in rows if r['config']==cfg['name'] and r['repeat']>1]; lats=sorted(r['latency_ms'] for r in subset); wers=[r['wer'] for r in subset]
 summary.append({'config':cfg['name'],'model':cfg['model'],'load_ms':round(load_ms,2),'warm_runs':len(subset),'mean_wer':round(statistics.mean(wers),4),'p50_stt_ms':nearest_rank(lats,.5),'p95_stt_ms':nearest_rank(lats,.95),'max_rss_mb':max(r['rss_mb'] for r in subset),'cpu':'CPU-only','gpu':'none'})
(ROOT/'artifacts/stt_comparison.json').write_text(json.dumps({'configs':summary,'runs':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
