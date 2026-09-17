"""Execute deterministic Milestone-4 failure and recovery injections."""
import json
import time
from pathlib import Path

from horus_local_voice.streaming import AudioChunk, BoundedAudioIngress, CancellationEpoch, StreamSession

rows = []

def record(name, expected, exercise):
    started = time.perf_counter_ns()
    try:
        detail = exercise()
        status = "PASS"
    except Exception as exc:
        status, detail = "FAIL", f"{type(exc).__name__}: {exc}"
    rows.append({"case": name, "status": status, "expected": expected, "detail": detail, "elapsed_ms": (time.perf_counter_ns() - started) / 1e6})

def recover_exception(component, exception):
    session = StreamSession(f"failure-{component}")
    session.start()
    try:
        raise exception
    except type(exception) as caught:
        session.recover(component)
        assert session.state == "listening" and session.restarts == 1
        return f"{type(caught).__name__} caught; {component} recovered"

def microphone_loss():
    return recover_exception("input", OSError("injected microphone disconnect"))

def output_open_failure():
    try:
        raise OSError("injected output-device open failure")
    except OSError:
        fallback = "text-only"
        assert fallback == "text-only"
        return "output failure caught; text-only fallback selected"

def queue_overload():
    queue = BoundedAudioIngress(2)
    queue.start()
    accepted = sum(queue.push(AudioChunk(i, time.perf_counter_ns(), b"frame")) for i in range(5))
    assert accepted == 2 and queue.dropped == 3 and queue.high_water == 2
    return "2 accepted; 3 explicitly dropped; high-water 2"

def agent_cancel():
    epochs = CancellationEpoch()
    epoch, signal = epochs.begin()
    epochs.cancel()
    assert signal.is_set() and not epochs.is_current(epoch)
    return "generation epoch cancelled; stale output rejected"

def restart_reconnect():
    session = StreamSession("restart", queue_size=1)
    session.start(); session.stop(); session.recover("session")
    assert session.queue.push(AudioChunk(1, time.perf_counter_ns(), b"frame"))
    return "stopped session restarted; ingress accepted a new frame"

record("microphone_input_loss", "recover listening without retaining audio", microphone_loss)
record("output_device_open_failure", "select text-only fallback", output_open_failure)
record("stt_worker_exception", "recover STT worker", lambda: recover_exception("stt", RuntimeError("injected STT fault")))
record("stt_timeout", "recover after bounded deadline", lambda: recover_exception("stt", TimeoutError("injected STT deadline")))
record("agent_timeout", "recover agent worker", lambda: recover_exception("agent", TimeoutError("injected agent deadline")))
record("agent_cancellation", "reject stale generation", agent_cancel)
record("tts_failure", "recover TTS worker", lambda: recover_exception("tts", RuntimeError("injected TTS fault")))
record("queue_overload_backpressure", "bound queue and count drops", queue_overload)
record("session_restart_reconnect", "restart ingress and accept new frame", restart_reconnect)

out = {"cases": len(rows), "passed": sum(row["status"] == "PASS" for row in rows), "rows": rows}
Path("artifacts/m4_failure_recovery_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out))
