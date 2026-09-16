import json
import statistics
import time
from pathlib import Path
import psutil
from faster_whisper import WhisperModel
from llama_cpp import Llama
from piper import PiperVoice
from horus_local_voice.real_audio import nearest_rank, webrtc_vad_wav

manifest=json.loads(Path("artifacts/audio_manifest.json").read_text(encoding="utf-8")); by={Path(x["file"]).name:x for x in manifest}; files=sorted(Path("artifacts/audio").glob("*.wav")); proc=psutil.Process()
t=time.perf_counter(); stt=WhisperModel("base",device="cpu",compute_type="int8"); stt_load=(time.perf_counter()-t)*1000
t=time.perf_counter(); agent=Llama(model_path="artifacts/models/qwen2.5-1.5b-instruct-q4_k_m.gguf",n_ctx=2048,n_threads=8,n_gpu_layers=0,verbose=False); agent_load=(time.perf_counter()-t)*1000
t=time.perf_counter(); tts=PiperVoice.load("artifacts/voices/ar_JO-kareem-medium.onnx"); tts_load=(time.perf_counter()-t)*1000
history=[{"role":"system","content":"أنت هورس. رد بجملة قصيرة بنفس لغة المستخدم ولا تستخدم أدوات."}]; rows=[]
for i in range(30):
 path=files[i%len(files)]; total=time.perf_counter(); vad=webrtc_vad_wav(path); lang=None if "english" in path.name else "ar"
 t=time.perf_counter(); segs,info=stt.transcribe(str(path),language=lang,beam_size=5,vad_filter=False); text=" ".join(x.text.strip() for x in segs).strip(); stt_ms=(time.perf_counter()-t)*1000
 history.append({"role":"user","content":text}); stream=agent.create_chat_completion(messages=history[-9:] if len(history)>9 else history,max_tokens=24,temperature=.1,stream=True); t=time.perf_counter(); first=None; reply=""
 for chunk in stream:
  token=chunk["choices"][0]["delta"].get("content","")
  if token and first is None: first=(time.perf_counter()-t)*1000
  reply+=token
 agent_ms=(time.perf_counter()-t)*1000; history.append({"role":"assistant","content":reply}); t=time.perf_counter(); chunks=tts.synthesize(reply or "تعذر الرد"); first_chunk=next(chunks); tts_first=(time.perf_counter()-t)*1000; chunk_count=1
 for _ in chunks: chunk_count+=1
 tts_total=(time.perf_counter()-t)*1000
 rows.append({"turn":i+1,"file":path.name,"vad_ms":vad.latency_ms,"stt_ms":stt_ms,"agent_first_token_ms":first or agent_ms,"agent_total_ms":agent_ms,"tts_first_audio_ms":tts_first,"tts_total_ms":tts_total,"end_to_end_ms":(time.perf_counter()-total)*1000,"transcript":text,"reply":reply,"tts_chunks":chunk_count})
def stats(key):
 vals=[x[key] for x in rows]; return {"p50":round(statistics.median(vals),2),"p95":round(nearest_rank(vals,.95),2),"min":round(min(vals),2),"max":round(max(vals),2)}
out={"turns":30,"pipeline":"WebRTC VAD -> faster-whisper base/int8 forced-ar beam5 -> Qwen2.5-1.5B Q4_K_M CPU -> Piper kareem-medium","cold_load_ms":{"stt":round(stt_load,2),"agent":round(agent_load,2),"tts":round(tts_load,2)},"metrics":{k:stats(k) for k in ["vad_ms","stt_ms","agent_first_token_ms","tts_first_audio_ms","end_to_end_ms"]},"rss_mb":round(proc.memory_info().rss/2**20,1),"gpu":"not used","rows":rows}
Path("artifacts/m3_e2e_results.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps({k:v for k,v in out.items() if k!="rows"},ensure_ascii=False))
