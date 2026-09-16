import json
import statistics
import time
import wave
from pathlib import Path
import psutil
from piper import PiperVoice
phrases=[("arabic","مرحباً بك في نظام هورس الذكي."),("arabic","يمكنني مساعدتك في تنظيم مهامك اليومية."),("arabic","هذه تجربة واضحة للصوت العربي المحلي."),("egyptian","أهلاً يا هورس، عامل إيه النهارده؟"),("egyptian","ممكن تساعدني أرتب يومي بسرعة؟"),("english","Hello HORUS, this is a local voice test."),("english","Please summarize today tasks clearly.")]
voices=[("piper_kareem_medium",Path("artifacts/voices/ar_JO-kareem-medium.onnx")),("piper_kareem_low",Path("artifacts/voices/ar_JO-kareem-low.onnx"))]
out=[]; proc=psutil.Process()
for name,path in voices:
 started=time.perf_counter(); voice=PiperVoice.load(str(path)); load_ms=(time.perf_counter()-started)*1000
 voice.synthesize("إحماء").__next__()
 rows=[]
 for i,(category,text) in enumerate(phrases):
  started=time.perf_counter(); chunks=voice.synthesize(text); first=next(chunks); first_ms=(time.perf_counter()-started)*1000; audio=bytearray(first.audio_int16_bytes)
  for chunk in chunks: audio.extend(chunk.audio_int16_bytes)
  total_ms=(time.perf_counter()-started)*1000; target=Path("artifacts/tts_m3")/f"{name}_{i}.wav"; target.parent.mkdir(parents=True,exist_ok=True)
  with wave.open(str(target),"wb") as w: w.setnchannels(first.sample_channels); w.setsampwidth(first.sample_width); w.setframerate(first.sample_rate); w.writeframes(audio)
  duration=len(audio)/(first.sample_rate*first.sample_width*first.sample_channels)
  rows.append({"category":category,"text":text,"first_audio_ms":round(first_ms,2),"synthesis_ms":round(total_ms,2),"output_s":round(duration,3),"rtf":round(total_ms/1000/duration,3),"rss_mb":round(proc.memory_info().rss/2**20,1),"file":str(target)})
 out.append({"voice":name,"model_bytes":path.stat().st_size,"load_ms":round(load_ms,2),"source":"rhasspy/piper-voices ar_JO/kareem","license_note":"upstream model card refers to dataset repository; redistribution terms require review","first_audio_p50_ms":round(statistics.median(x["first_audio_ms"] for x in rows),2),"rtf_p50":round(statistics.median(x["rtf"] for x in rows),3),"rows":rows})
Path("artifacts/m3_tts_comparison.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps([{k:v for k,v in x.items() if k!="rows"} for x in out],ensure_ascii=False))
