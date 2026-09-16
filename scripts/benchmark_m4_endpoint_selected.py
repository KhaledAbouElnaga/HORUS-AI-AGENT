import audioop, json, time, wave
from pathlib import Path
import webrtcvad
from horus_local_voice.streaming import EndpointPolicy, detect_endpoint
from horus_local_voice.real_audio import nearest_rank
files=sorted(Path("artifacts/audio").glob("*.wav"))+sorted(Path("artifacts/m4_language_audio").glob("*.wav"))
files=(files*3)[:40]; rows=[]
for trial,path in enumerate(files,1):
 with wave.open(str(path),"rb") as w: rate=w.getframerate(); pcm=w.readframes(w.getnframes())
 if rate!=16000: pcm,_,=audioop.ratecv(pcm,2,1,rate,16000,None); rate=16000
 size=960; vad=webrtcvad.Vad(2); flags=[vad.is_speech(pcm[i:i+size],rate) for i in range(0,len(pcm)-size+1,size)]
 if trial%3==0 and len(flags)>30: flags=flags[:len(flags)//2]+[False]*8+flags[len(flags)//2:]
 started=time.perf_counter(); result=detect_endpoint(flags+[False]*40,EndpointPolicy("robust-1200ms",3,40,1000)); endpoint=result.end_frame
 later=result.false_cut
 rows.append({"trial":trial,"file":path.name,"false_cut":later,"endpoint_frame":endpoint,"compute_ms":(time.perf_counter()-started)*1000})
out={"policy":"robust-1200ms","trials":40,"false_cuts":sum(x["false_cut"] for x in rows),"tail_ms":1200,"compute_p95_ms":nearest_rank([x["compute_ms"] for x in rows],.95),"rows":rows}; Path("artifacts/m4_endpoint_selected.json").write_text(json.dumps(out,indent=2),encoding="utf-8"); print(json.dumps({k:v for k,v in out.items() if k!="rows"}))
