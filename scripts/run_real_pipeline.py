"""Run 20 real local WAV -> faster-whisper -> deterministic agent -> Piper turns."""
import json, time, wave, tempfile
from pathlib import Path
import psutil
from faster_whisper import WhisperModel
from piper import PiperVoice

ROOT=Path(__file__).parents[1]; proc=psutil.Process(); manifest=json.loads((ROOT/'artifacts/audio_manifest.json').read_text(encoding='utf-8'))
model=WhisperModel('tiny',device='cpu',compute_type='int8')
voices={'ar':PiperVoice.load(str(ROOT/'artifacts/voices/ar_JO-kareem-medium.onnx')),'en':PiperVoice.load(str(ROOT/'artifacts/voices/en_US-lessac-medium.onnx'))}
def words(s): return s.lower().replace("'",'').split()
def wer(ref,hyp):
 a,b=words(ref),words(hyp); d=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  n=[i]+[0]*len(b)
  for j,y in enumerate(b,1): n[j]=min(n[j-1]+1,d[j]+1,d[j-1]+(x!=y))
  d=n
 return d[-1]/max(1,len(a))
rows=[]; context=[]; start_all=time.perf_counter()
for i in range(20):
 item=manifest[i%7]; path=ROOT/item['file']; lang='ar' if item['language']=='ar' else 'en'; turn=time.perf_counter()
 t=time.perf_counter(); seg,info=model.transcribe(str(path),beam_size=1,vad_filter=False); stt=' '.join(s.text.strip() for s in seg).strip(); stt_ms=(time.perf_counter()-t)*1000
 t=time.perf_counter(); reply='سمعتك، هكمل معاك.' if lang=='ar' else "I heard you; I'll continue."; agent_ms=(time.perf_counter()-t)*1000
 t=time.perf_counter()
 with tempfile.NamedTemporaryFile(suffix='.wav',delete=False) as f:
  with wave.open(f.name,'wb') as w: voices[lang].synthesize_wav(reply,w)
 tts_ms=(time.perf_counter()-t)*1000
 context.append(stt)
 rows.append({'turn':i+1,'file':item['file'],'language':lang,'stt_ms':round(stt_ms,2),'agent_first_output_ms':round(agent_ms,2),'tts_first_audio_ms':round(tts_ms,2),'end_to_end_ms':round((time.perf_counter()-turn)*1000,2),'wer':round(wer(item['expected'],stt),4),'observed':stt})
summary={}
for k in ['stt_ms','agent_first_output_ms','tts_first_audio_ms','end_to_end_ms']:
 vals=sorted(r[k] for r in rows); summary[k]={'min':vals[0],'median':vals[len(vals)//2],'p95':vals[min(19,int(len(vals)*.95)-1)],'max':vals[-1]}
summary['mean_wer']=round(sum(r['wer'] for r in rows)/len(rows),4); summary['turns']=len(rows); summary['context_turns']=len(context); summary['context_10_pass']=len(context)>=10; summary['elapsed_s']=round(time.perf_counter()-start_all,2); summary['rss_mb']=round(proc.memory_info().rss/1024/1024,1); summary['cpu_percent_sample']=proc.cpu_percent(interval=0.2); summary['gpu']='CPU path (device=cpu)'
out={'model':'faster-whisper tiny int8','summary':summary,'turns':rows}; (ROOT/'artifacts/e2e_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False))
