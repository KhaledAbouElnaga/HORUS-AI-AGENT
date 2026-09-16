"""Unretained microphone smoke/latency trials; captures are discarded immediately."""
import json,time
from pathlib import Path
import numpy as np
import sounddevice as sd

rows=[]
for trial in range(10):
    started=time.perf_counter()
    try:
        audio=sd.rec(int(0.25*16000),samplerate=16000,channels=1,dtype='int16',blocking=True)
        rms=float(np.sqrt(np.mean(audio.astype(np.float32)**2)))
        rows.append({'trial':trial+1,'status':'PASS','capture_ms':round((time.perf_counter()-started)*1000,2),'rms':round(rms,2)})
        del audio
    except Exception as exc:
        rows.append({'trial':trial+1,'status':'BLOCKED','error':type(exc).__name__+': '+str(exc)[:120]})
        break
out={'trials_requested':10,'trials_completed':len(rows),'all_pass':len(rows)==10 and all(x['status']=='PASS' for x in rows),'raw_audio_retained':False,'rows':rows}
Path('artifacts/live_device_results.json').write_text(json.dumps(out,indent=2),encoding='utf-8'); print(json.dumps(out))
