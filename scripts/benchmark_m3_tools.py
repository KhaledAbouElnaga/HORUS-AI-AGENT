import json
import statistics
import time
from pathlib import Path
from llama_cpp import Llama
model=Path("artifacts/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"); llm=Llama(model_path=str(model),n_ctx=2048,n_threads=8,n_gpu_layers=0,verbose=False)
cases=[("احسب 14 زائد 9","calculator"),("ابحث في الذاكرة عن اسمي","memory_search"),("اعرض حالة النظام","status"),("احفظ ملاحظة اجتماع الخميس","memory_write"),("اقرأ ملف demo.txt","file_read")]*4
system="اختر أداة واحدة فقط من calculator,memory_search,status,memory_write,file_read. أعد JSON فقط بالمفتاحين tool و args. لا تنفذ الأداة بنفسك."
rows=[]
for prompt,expected in cases:
 t=time.perf_counter(); response=llm.create_chat_completion(messages=[{"role":"system","content":system},{"role":"user","content":prompt}],max_tokens=64,temperature=0,response_format={"type":"json_object","schema":{"type":"object","properties":{"tool":{"type":"string","enum":["calculator","memory_search","status","memory_write","file_read"]},"args":{"type":"object"}},"required":["tool","args"]}}); elapsed=(time.perf_counter()-t)*1000; raw=response["choices"][0]["message"]["content"]
 try: parsed=json.loads(raw); chosen=parsed.get("tool"); valid_args=isinstance(parsed.get("args"),dict)
 except Exception: chosen=None; valid_args=False
 matched=chosen==expected and valid_args
 mock={"calculator":23,"memory_search":[],"status":{"ok":True},"memory_write":{"persisted":False},"file_read":"demo"}.get(chosen) if matched else None
 rows.append({"prompt":prompt,"expected":expected,"raw":raw,"chosen":chosen,"valid":matched,"mock_execution":mock,"latency_ms":round(elapsed,2)})
out={"model":"Qwen2.5-1.5B-Instruct Q4_K_M","actions":len(rows),"valid_actions":sum(x["valid"] for x in rows),"fail_closed":all(x["mock_execution"] is None for x in rows if not x["valid"]),"median_ms":round(statistics.median(x["latency_ms"] for x in rows),2),"rows":rows}; Path("artifacts/m3_tool_actions.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps({k:v for k,v in out.items() if k!="rows"},ensure_ascii=False))
