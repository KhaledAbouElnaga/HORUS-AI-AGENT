import json
import time
from pathlib import Path
import numpy as np
import sounddevice as sd
out={"default":list(sd.default.device),"devices":[{"index":i,"name":d["name"],"inputs":d["max_input_channels"],"outputs":d["max_output_channels"],"rate":d["default_samplerate"]} for i,d in enumerate(sd.query_devices())]}
try:
 t=time.perf_counter(); data=sd.rec(4000,samplerate=16000,channels=1,dtype="int16",blocking=True); out["input_probe"]={"pass":True,"ms":round((time.perf_counter()-t)*1000,2),"frames_discarded":len(data),"peak":int(abs(data).max())}
except Exception as exc: out["input_probe"]={"pass":False,"error":str(exc)}
try:
 t=time.perf_counter(); sd.play(np.zeros(3200,dtype=np.int16),16000,blocking=True); out["output_probe"]={"pass":True,"ms":round((time.perf_counter()-t)*1000,2),"frames":3200,"content":"silence"}
except Exception as exc: out["output_probe"]={"pass":False,"error":str(exc)}
Path("artifacts/m3_audio_devices.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps({"device_count":len(out["devices"]),"default":out["default"],"input_probe":out["input_probe"],"output_probe":out["output_probe"]},ensure_ascii=False))
