"""Run the project-local Qwen GGUF through Arabic, English, mixed, memory, and tool-intent cases."""
import json
import time
from pathlib import Path
import psutil
from llama_cpp import Llama

model_path = Path("artifacts/models/qwen2.5-0.5b-instruct-q4_k_m.gguf")
proc = psutil.Process(); rss0 = proc.memory_info().rss
started=time.perf_counter(); llm=Llama(model_path=str(model_path), n_ctx=2048, n_threads=8, n_gpu_layers=0, verbose=False); load_ms=(time.perf_counter()-started)*1000
system={"role":"system","content":"أنت هورس، مساعد مختصر وآمن. رد بنفس لغة المستخدم. لا تدّعي تنفيذ أدوات."}
ar=["إزيك النهارده؟","اشرح الذكاء الاصطناعي ببساطة","اديني ثلاث نصائح لتنظيم الوقت","إيه الفرق بين الجامعة والمعهد؟","لخص أهمية النوم","اكتب ترحيب قصير","إزاي أحافظ على تركيزي؟","اقترح خطة مذاكرة يومية","ما معنى الخصوصية الرقمية؟","رد باختصار: ليه الاختبار مهم؟"]
en=["Explain local AI in one sentence.","Give two study tips.","What is a safe fallback?","Write a short greeting.","Why measure latency?"]
mixed=["عايز summary سريع عن AI","اشرح latency بالمصري","اديني plan للمذاكرة","إيه معنى privacy by design؟","اعمل checklist قصيرة للاختبار"]
rows=[]
def run(prompt, category, messages=None, max_tokens=48):
    msgs=messages or [system,{"role":"user","content":prompt}]
    started=time.perf_counter(); first=None; text=""; completion=0
    for chunk in llm.create_chat_completion(messages=msgs,max_tokens=max_tokens,temperature=0.1,stream=True):
        token=chunk["choices"][0]["delta"].get("content","")
        if token and first is None: first=(time.perf_counter()-started)*1000
        text += token; completion += 1 if token else 0
    elapsed=time.perf_counter()-started
    row={"category":category,"prompt":prompt,"response":text,"first_token_ms":round(first or elapsed*1000,2),"elapsed_ms":round(elapsed*1000,2),"stream_chunks_per_s":round(completion/elapsed,2),"rss_mb":round(proc.memory_info().rss/2**20,1)}; rows.append(row); return text
for p in ar: run(p,"arabic")
for p in en: run(p,"english")
for p in mixed: run(p,"mixed")
mem=[system]
for i in range(1,11):
    prompt="تذكر أن الرقم السري التجريبي هو 7319. ما الرقم؟" if i==1 else ("ما الرقم الذي طلبت منك تذكره؟" if i==10 else f"هذه رسالة المتابعة رقم {i}. أكد باختصار.")
    mem.append({"role":"user","content":prompt}); answer=run(prompt,"memory",mem,max_tokens=32); mem.append({"role":"assistant","content":answer})
tools=[("احسب 2+3 باستخدام أداة calculator فقط","calculator"),("ابحث في الذاكرة عن اسمي","memory_search"),("اعرض حالة النظام بأداة status","status"),("احفظ الملاحظة اختبار في الذاكرة","memory_write"),("اقرأ الملف الوهمي demo.txt","file_read")]
tool_results=[]
for prompt,expected in tools:
    response=run(prompt+". أخرج JSON يحتوي حقلي tool و args","tool_intent",max_tokens=48)
    matched=expected in response
    safe_result={"calculator":5,"memory_search":[],"status":"mock-ok","memory_write":"mock-not-persisted","file_read":"mock-content"}.get(expected)
    tool_results.append({"expected":expected,"matched":matched,"mock_result":safe_result})
import statistics
out={"runtime":"llama-cpp-python 0.3.35 CPU","model":"Qwen2.5-0.5B-Instruct Q4_K_M","source":"https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF","license":"Apache-2.0 per upstream repository","model_bytes":model_path.stat().st_size,"load_ms":round(load_ms,2),"rss_delta_mb":round((proc.memory_info().rss-rss0)/2**20,1),"first_token_median_ms":round(statistics.median(x["first_token_ms"] for x in rows),2),"throughput_median_chunks_s":round(statistics.median(x["stream_chunks_per_s"] for x in rows),2),"memory_turn_10_pass":"7319" in rows[-6]["response"],"tool_intents_matched":sum(x["matched"] for x in tool_results),"tool_results":tool_results,"rows":rows}
Path("artifacts/m3_agent_results.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in out.items() if k not in ["rows"]},ensure_ascii=False))
