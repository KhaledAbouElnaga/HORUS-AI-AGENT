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
from horus_local_voice.streaming import StreamSession, script_route

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

stt = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=1)
stt.transcribe(str(items[0][0]), beam_size=1)
candidates=[]
for name,fraction,beam,windowed in (("rolling-50-beam1",.5,1,False),("windowed-75-beam5",.75,5,True)):
 rows=[]
 for path,reference,category in items:
  partial_path=wav_prefix(path,fraction,3.0 if windowed else None); started=time.perf_counter(); seg,_=stt.transcribe(str(partial_path),beam_size=beam,language=None if category=="english" else "ar"); partial=" ".join(x.text.strip() for x in seg).strip(); first_ms=(time.perf_counter()-started)*1000; partial_path.unlink(missing_ok=True)
  started=time.perf_counter(); seg,_=stt.transcribe(str(path),beam_size=beam,language=None if category=="english" else "ar"); final=" ".join(x.text.strip() for x in seg).strip(); final_ms=(time.perf_counter()-started)*1000
  rows.append({"file":path.name,"category":category,"partial":partial,"final":final,"first_partial_compute_ms":first_ms,"finalization_ms":final_ms,"wer":word_error_rate(reference,final),"duplicate_accumulation":False})
 candidates.append({"candidate":name,"turns":len(rows),"first_partial_p50_ms":statistics.median(x["first_partial_compute_ms"] for x in rows),"first_partial_p95_ms":nearest_rank([x["first_partial_compute_ms"] for x in rows],.95),"final_p50_ms":statistics.median(x["finalization_ms"] for x in rows),"final_p95_ms":nearest_rank([x["finalization_ms"] for x in rows],.95),"mean_wer":statistics.mean(x["wer"] for x in rows),"rss_mb":psutil.Process().memory_info().rss/2**20,"rows":rows})
Path("artifacts/m4_stt_candidates_checkpoint.json").write_text(json.dumps(candidates,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps([{k:v for k,v in x.items() if k!="rows"} for x in candidates]))
