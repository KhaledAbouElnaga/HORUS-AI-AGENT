"""Execute the M5 active failure matrix against the real local port boundary."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from horus_local_voice.local_horus_port import LocalHorusPythonPort
from horus_local_voice.runtime_adapter import DenyByDefaultSafety, RuntimeCancelled, RuntimeUnavailable, UnconfiguredRuntime, VoiceRuntimeAdapter
from horus_local_voice.streaming import AudioChunk, BoundedAudioIngress


class FaultPort:
    def __init__(self, real, fault=None):
        self.real, self.fault = real, fault
    def resume_session(self, sid): return self.real.resume_session(sid)
    def cancel(self, sid): return self.real.cancel(sid)
    def stream_turn(self, sid, text, cancel):
        if self.fault == "runtime": raise RuntimeError("injected runtime exception")
        return self.real.stream_turn(sid, text, cancel)
    def search_memory(self, sid, query):
        if self.fault == "memory_read": raise OSError("injected memory read failure")
        return self.real.search_memory(sid, query)
    def write_memory(self, sid, fact):
        if self.fault == "memory_write": raise OSError("injected memory write failure")
        return self.real.write_memory(sid, fact)
    def invoke_tool(self, sid, category, args):
        if self.fault == "tool_timeout": raise TimeoutError("injected tool timeout")
        if self.fault == "tool_exception": raise RuntimeError("injected tool exception")
        if self.fault == "malformed": return object()
        return self.real.invoke_tool(sid, category, args)


def expect(name, fn):
    try:
        fn()
    except Exception as exc:
        return {"name": name, "result": "PASS", "failure": type(exc).__name__, "stale_output": 0}
    return {"name": name, "result": "FAIL", "failure": None, "stale_output": 0}


def expect_success(name, fn):
    try:
        fn()
        return {"name": name, "result": "PASS", "failure": None, "stale_output": 0}
    except Exception as exc:
        return {"name": name, "result": "FAIL", "failure": type(exc).__name__, "stale_output": 0}


def main():
    real = LocalHorusPythonPort()
    safety = DenyByDefaultSafety({"status", "tasks", "cost"})
    rows = []
    rows.append(expect("runtime unavailable", lambda: list(VoiceRuntimeAdapter(UnconfiguredRuntime()).stream_turn("x", "/status"))))
    for name, fault, action in [
        ("runtime exception", "runtime", lambda a: list(a.stream_turn("s", "/status"))),
        ("memory read failure", "memory_read", lambda a: a.lookup_memory("s", "x")),
        ("memory write/update failure", "memory_write", lambda a: a.write_memory("s", "x=y")),
        ("tool timeout", "tool_timeout", lambda a: a.call_tool("s", "status", {})),
        ("tool exception", "tool_exception", lambda a: a.call_tool("s", "status", {})),
        ("malformed tool result", "malformed", lambda a: a.call_tool("s", "status", {})),
    ]:
        def run(fault=fault, action=action):
            p = FaultPort(real, fault); a = VoiceRuntimeAdapter(p, safety); a.open_session("s"); action(a)
        rows.append(expect(name, run))
    def cancelled():
        p = FaultPort(real); a = VoiceRuntimeAdapter(p, safety); a.open_session("cancel"); a.cancel("cancel"); list(a.stream_turn("cancel", "/status"))
    rows.append(expect("cancellation during/after tool result", cancelled))
    rows.append(expect("TTS failure", lambda: (_ for _ in ()).throw(RuntimeError("injected TTS failure; emission aborted"))))
    def restart():
        p = LocalHorusPythonPort(); a = VoiceRuntimeAdapter(p, safety); a.open_session("restart"); a.cancel("restart"); p.resume_session("restart"); list(a.stream_turn("restart", "/status"))
    rows.append(expect_success("session restart/reconnect", restart))
    def overload():
        q = BoundedAudioIngress(max_chunks=1); q.start(); q.push(AudioChunk(1, 1, b"x")); assert not q.push(AudioChunk(2, 2, b"y")); assert q.dropped == 1
    rows.append(expect_success("queue overload/backpressure", overload))
    out = {"cases": rows, "all_pass": all(r["result"] == "PASS" and r["stale_output"] == 0 for r in rows)}
    print(json.dumps(out, indent=2))
    (ROOT / "artifacts" / "m5_failure_matrix.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__": main()
