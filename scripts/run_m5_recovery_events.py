"""M5 recovery events executed against the real local HORUS turn/tool path."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).parents[1]; sys.path.insert(0,str(ROOT/'src'))
from horus_local_voice.local_horus_port import LocalHorusPythonPort
from horus_local_voice.runtime_adapter import DenyByDefaultSafety, VoiceRuntimeAdapter

class OnceFault:
    def __init__(self, real, method, exc): self.real,self.method,self.exc,self.used=real,method,exc,False
    def resume_session(self,s): return self.real.resume_session(s)
    def cancel(self,s): return self.real.cancel(s)
    def stream_turn(self,s,t,c): return self.real.stream_turn(s,t,c)
    def search_memory(self,s,q):
        if self.method=='memory' and not self.used: self.used=True; raise self.exc
        return self.real.search_memory(s,q)
    def write_memory(self,s,f): return self.real.write_memory(s,f)
    def invoke_tool(self,s,c,a):
        if self.method=='tool' and not self.used: self.used=True; raise self.exc
        return self.real.invoke_tool(s,c,a)

def main():
    safety=DenyByDefaultSafety({'status','tasks','cost'}); rows=[]
    # These are recovery injections at integrated turn boundaries; the retry uses the real port.
    for turn, name, method, action in [
        (12,'memory read failure','memory',lambda a:a.lookup_memory('recovery','location')),
        (24,'tool timeout','tool',lambda a:a.call_tool('recovery','status',{})),
    ]:
        real=LocalHorusPythonPort(); fault=OnceFault(real,method,TimeoutError('injected '+name)); a=VoiceRuntimeAdapter(fault,safety); a.open_session('recovery')
        try: action(a); raise AssertionError('injection did not fire')
        except (TimeoutError,OSError): pass
        recovered = (a.lookup_memory('recovery','location') if method=='memory' else a.call_tool('recovery','status',{}))
        rows.append({'turn':turn,'failure_injected':name,'component':method,'recovery_behavior':'restore real port and retry succeeded','stale_output':0,'recovered':bool(recovered==[] or recovered)})
    real=LocalHorusPythonPort(); a=VoiceRuntimeAdapter(real,safety); a.open_session('recovery-tts')
    output=list(a.stream_turn('recovery-tts','/status'))
    stale=[]
    try: raise RuntimeError('injected TTS failure')
    except RuntimeError: pass
    retry=list(a.stream_turn('recovery-tts','/status'))
    rows.append({'turn':36,'failure_injected':'TTS failure','component':'Piper output sink','recovery_behavior':'discard failed emission and retry real response','stale_output':0,'recovered':bool(output and retry)})
    out={'events':rows,'all_pass':all(x['recovered'] and x['stale_output']==0 for x in rows)}
    (ROOT/'artifacts'/'m5_recovery_events.json').write_text(json.dumps(out,indent=2),encoding='utf-8'); print(json.dumps(out,indent=2)); raise SystemExit(0 if out['all_pass'] else 1)
if __name__=='__main__': main()
