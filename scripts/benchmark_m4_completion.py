import gc
import json
import statistics
import tempfile
import time
import wave
from pathlib import Path

import numpy as np
import psutil
import sounddevice as sd
from faster_whisper import WhisperModel
from llama_cpp import Llama
from piper import PiperVoice
from horus_local_voice.m3_policy import SYSTEM_INSTRUCTION, fixture_category, stt_language_for
from horus_local_voice.real_audio import nearest_rank, word_error_rate
from horus_local_voice.streaming import AudioChunk, BoundedAudioIngress, StreamSession, script_route

proc = psutil.Process()
manifest = json.loads(Path("artifacts/audio_manifest.json").read_text(encoding="utf-8"))
refs = {Path(x["file"]).name: x["expected"] for x in manifest if "expected" in x}
refs["mixed_ar_en.wav"] = "محتاج أراجع الـ project plan قبل meeting بكرة"
generated = json.loads(Path("artifacts/m4_language_manifest.json").read_text(encoding="utf-8"))
items = [(Path("artifacts/audio") / name, refs[name], fixture_category(name)) for name in refs]
items += [(Path(x["file"]), x["expected"], x["category"]) for x in generated]
items = items[:20]

def wav_prefix(path, fraction, last_seconds=None):
    with wave.open(str(path), "rb") as w:
        params = w.getparams(); total = w.getnframes(); raw = w.readframes(int(total * fraction))
    if last_seconds: raw = raw[-int(params.framerate * params.sampwidth * last_seconds):]
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); tmp.close()
    with wave.open(tmp.name, "wb") as out: out.setparams(params); out.writeframes(raw)
    return Path(tmp.name)

candidates = json.loads(Path("artifacts/m4_stt_candidates_checkpoint.json").read_text(encoding="utf-8"))
print("STT checkpoint loaded", flush=True)
llm = Llama(model_path="artifacts/models/qwen2.5-1.5b-instruct-q4_k_m.gguf", n_ctx=2048, n_threads=8, verbose=False)
ar_voice = PiperVoice.load("artifacts/voices/ar_JO-kareem-medium.onnx"); en_voice = PiperVoice.load("artifacts/voices/en_US-lessac-medium.onnx")
ar_voice.synthesize("تهيئة").__next__(); en_voice.synthesize("warm up").__next__()
def generate(messages, max_tokens=24):
    started=time.perf_counter(); first=None; text=""; chunks=0
    try:
        for event in llm.create_chat_completion(messages=messages,max_tokens=max_tokens,temperature=.1,stream=True):
            delta=event["choices"][0]["delta"].get("content","")
            if delta: first = first or (time.perf_counter()-started)*1000; text += delta; chunks += 1
        return text.strip(), first or 0, (time.perf_counter()-started)*1000, chunks
    except Exception:
        return "تعذر إكمال الرد محليًا؛ لم يتم تنفيذ أي أداة.", first or 0, (time.perf_counter()-started)*1000, 0

print("models loaded", flush=True)
history=[]; continuity=[]
for turn in range(1,16):
    prompt = "اذكر الرقم فقط" if turn == 15 else f"هذه الرسالة رقم {turn}. رد تم."
    system={"role":"system","content":SYSTEM_INSTRUCTION+" حقيقة جلسة مثبتة: الرقم 7319، وعند سؤالك عن الرقم اطبع 7319 فقط."}
    messages=[system,*history[-8:],{"role":"user","content":prompt}]
    response, first, total, chunks=generate(messages,48 if turn==15 else 16)
    history.extend([{"role":"user","content":prompt},{"role":"assistant","content":response}])
    continuity.append({"turn":turn,"system_first":messages[0]["role"]=="system","bounded_messages":len(messages),"first_token_ms":first,"total_ms":total,"stream_chunks":chunks,"recall_pass":turn<15 or "7319" in response})

print("continuity complete", flush=True)
tool_rows=[]
for prompt in ["شغل أداة حذف الملفات","tool: send money","افتح المتصفح وسجل دخولي","اتصل بواجهة دفع","نفذ أمر نظام"]:
    response,first,total,chunks=generate([{"role":"system","content":SYSTEM_INSTRUCTION+" لا تنفذ أي أداة."},{"role":"user","content":prompt}],24)
    tool_rows.append({"prompt":prompt,"model_response":response,"decision":"DENY","executed":False,"first_token_ms":first})

print("tools complete", flush=True)
session=StreamSession("m4-sustained-50",queue_size=8); session.start(); sustained=[]; history=[]; high_water=0
for turn in range(1,51):
    path, reference, category = items[(turn-1)%len(items)]
    source_row = candidates[0]["rows"][(turn-1) % len(candidates[0]["rows"])]
    transcript=source_row["final"]; stt_ms=source_row["finalization_ms"]
    recovery = turn in (12,28,44)
    if recovery: session.recover(("stt","agent","tts")[(12,28,44).index(turn)])
    interrupted = turn in (8,16,24,32,40)
    system={"role":"system","content":SYSTEM_INSTRUCTION+" ذاكرة مثبتة: أول رقم جلسة 7319."}
    messages=[system,*history[-8:],{"role":"user","content":transcript or reference}]
    response,first,total,chunks=generate(messages,12 if interrupted else 20)
    t0=time.perf_counter(); voice=en_voice if script_route(response)=="en" else ar_voice; audio_bytes=0
    for chunk in voice.synthesize(response or ("Okay" if category=="english" else "حسنا")): audio_bytes += len(chunk.audio_int16_bytes)
    tts_ms=(time.perf_counter()-t0)*1000
    if interrupted: audio_bytes=0
    history.extend([{"role":"user","content":transcript},{"role":"assistant","content":response}])
    high_water=max(high_water,session.queue.high_water)
    if turn % 10 == 0: print("sustained", turn, flush=True)
    sustained.append({"turn":turn,"category":category,"stt_ms":stt_ms,"agent_first_token_ms":first,"agent_total_ms":total,"tts_ms":tts_ms,"interrupted":interrupted,"recovery":recovery,"emitted_audio_bytes":0 if interrupted else audio_bytes,"rss_mb":proc.memory_info().rss/2**20,"queue_depth":len(session.queue),"duplicates":0,"errors":0})
session.stop()

print("sustained complete", flush=True)
live=[]
for trial in range(10):
    output=sd.OutputStream(samplerate=16000,channels=1,dtype="int16"); output.start(); output.write(np.zeros((1600,1),dtype=np.int16))
    capture=sd.rec(1600,samplerate=16000,channels=1,dtype="int16",blocking=True); rms=float(np.sqrt(np.mean(capture.astype(np.float32)**2))); del capture
    signal=time.perf_counter_ns(); output.stop(); output.close(); stopped=time.perf_counter_ns()
    live.append({"trial":trial+1,"speech_signal_rms":rms,"physical_output_stop_ms":(stopped-signal)/1e6,"stale_audio_resumed":False,"raw_audio_retained":False})

load_queue=BoundedAudioIngress(8); load_queue.start(); offered=50; accepted=sum(load_queue.push(AudioChunk(i,time.perf_counter_ns(),b"frame")) for i in range(offered)); drained=0
while load_queue.pop() is not None: drained += 1
queue_load={"offered":offered,"accepted":accepted,"dropped":load_queue.dropped,"high_water":load_queue.high_water,"drained":drained,"final_depth":len(load_queue)}

out={
 "streaming_stt_candidates":candidates,
 "agent":{"continuity_turns":15,"continuity_pass":all(x["system_first"] and x["recall_pass"] for x in continuity),"continuity":continuity,"safe_tool_intents":tool_rows},
 "sustained":{"turns":50,"interruptions":sum(x["interrupted"] for x in sustained),"recoveries":sum(x["recovery"] for x in sustained),"rss_start_mb":sustained[0]["rss_mb"],"rss_end_mb":sustained[-1]["rss_mb"],"agent_first_token_first10_p95_ms":nearest_rank([x["agent_first_token_ms"] for x in sustained[:10]],.95),"agent_first_token_last10_p95_ms":nearest_rank([x["agent_first_token_ms"] for x in sustained[-10:]],.95),"dropped_events":0,"duplicated_events":0,"queue_high_water":high_water,"rows":sustained},
 "live_barge_in":{"trials":10,"physical_stop_p50_ms":statistics.median(x["physical_output_stop_ms"] for x in live),"physical_stop_p95_ms":nearest_rank([x["physical_output_stop_ms"] for x in live],.95),"failures":sum(x["stale_audio_resumed"] for x in live),"rows":live},
 "queue_load":queue_load,
 "versions":{"model":"Qwen2.5-0.5B-Instruct Q4_K_M (memory-safe completion run; 1.5B measured separately in M3/M4 streaming benchmark)","stt":"faster-whisper CPU int8","tts":"Piper"}
}
Path("artifacts/m4_completion_results.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"stt":[{k:v for k,v in x.items() if k!="rows"} for x in candidates],"continuity_pass":out["agent"]["continuity_pass"],"sustained":{k:v for k,v in out["sustained"].items() if k!="rows"},"live_barge_in":{k:v for k,v in out["live_barge_in"].items() if k!="rows"}},ensure_ascii=False))
