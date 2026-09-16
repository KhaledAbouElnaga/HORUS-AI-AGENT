"""Attempt a real local TinyLlama GGUF agent path through llama.cpp Python."""
import json,time,psutil
from pathlib import Path
from llama_cpp import Llama
ROOT=Path(__file__).parents[1]; path=ROOT/'artifacts/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf'; proc=psutil.Process()
load=time.perf_counter(); llm=Llama(model_path=str(path), n_ctx=512, n_threads=4, verbose=False); load_ms=(time.perf_counter()-load)*1000
prompts=['Respond briefly in Egyptian Arabic: إزيك يا هورس؟','Respond briefly in English: summarize this task.','Respond briefly in Arabic: فكرني بالاجتماع.']
rows=[]
for prompt in prompts:
 start=time.perf_counter(); result=llm(prompt,max_tokens=32,temperature=0,echo=False); elapsed=(time.perf_counter()-start)*1000; text=result['choices'][0]['text'].strip(); rows.append({'prompt':prompt,'output':text,'elapsed_ms':round(elapsed,2),'tokens':result['usage']['completion_tokens']})
out={'model':path.name,'load_ms':round(load_ms,2),'rss_mb':round(proc.memory_info().rss/1024/1024,1),'cpu_threads':4,'rows':rows}; (ROOT/'artifacts/llm_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(out,ensure_ascii=False))
