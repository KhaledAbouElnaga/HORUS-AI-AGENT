"""Live OpenAI Realtime preflight without WhatsApp or production media.

The report is deliberately transcript-free and contains only booleans, counts,
latencies, and a narrow status-tool summary.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from horus_local_voice.local_horus_port import LocalHorusPythonPort
from horus_local_voice.realtime_voice import REALTIME_MODEL, RealtimeTimeouts, RealtimeVoiceBridge


QUERY_AR = "ما اسمك؟"


def wait_until(predicate, timeout: float, label: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise TimeoutError(f"preflight timed out: {label}")


def ensure_piper_voice() -> Path:
    configured = os.environ.get("PIPER_AR_VOICE")
    if configured and Path(configured).is_file():
        return Path(configured)
    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "horus" / "realtime-preflight"
    base.mkdir(parents=True, exist_ok=True)
    model = base / "ar_JO-kareem-medium.onnx"
    config = base / "ar_JO-kareem-medium.onnx.json"
    source = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/"
    expected = {
        "ar_JO-kareem-medium.onnx": "9e95cab07b679da603bba17c4dec7ab3111320571964ee95c0379603c086491e",
        "ar_JO-kareem-medium.onnx.json": "ea6d9b9d9076dbdb6bf5c98c6a141ef154959d2359709b37855727964e7d6c4d",
    }
    for destination in (model, config):
        wanted = expected[destination.name]
        if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == wanted:
            continue
        temporary = destination.with_suffix(destination.suffix + ".part")
        urllib.request.urlretrieve(source + destination.name, temporary)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != wanted:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("preflight voice checksum verification failed")
        temporary.replace(destination)
    return model


def synthesize_fixture_48k() -> bytes:
    voice_path = ensure_piper_voice()
    from piper import PiperVoice
    import audioop

    voice = PiperVoice.load(voice_path)
    pcm = b"".join(chunk.audio_int16_bytes for chunk in voice.synthesize(QUERY_AR))
    if not pcm:
        raise RuntimeError("Arabic preflight fixture generation returned empty PCM")
    source_rate = int(getattr(voice.config, "sample_rate", 22_050))
    pcm48, _state = audioop.ratecv(pcm, 2, 1, source_rate, 48_000, None)
    if not pcm48:
        raise RuntimeError("Arabic preflight fixture resampling returned empty PCM")
    # A clear complete phrase plus 2.5 s of trailing silence gives semantic VAD
    # enough endpoint context without layering local endpointing.
    return (b"\0" * (48_000 * 2 * 2 // 5)) + pcm48 + (b"\0" * (48_000 * 2 * 5 // 2))


def stream_realtime(bridge: RealtimeVoiceBridge, pcm48: bytes) -> None:
    frame_bytes = 960 * 2  # exact WhatsApp OutputTrack-sized 20 ms mono PCM16 frames
    for offset in range(0, len(pcm48), frame_bytes):
        frame = pcm48[offset:offset + frame_bytes]
        if len(frame) < frame_bytes:
            frame += b"\0" * (frame_bytes - len(frame))
        bridge.on_pcm(frame, 48_000)
        time.sleep(0.02)


def drain_output_to_playout(bridge: RealtimeVoiceBridge) -> int:
    """Exercise the exact queued 48 kHz output boundary and echo guard."""
    forwarded = 0
    while True:
        item = bridge.next_output(timeout=0.05)
        if item is None:
            return forwarded
        pcm, rate = item
        if rate != 48_000:
            raise RuntimeError("Realtime output did not reach the 48 kHz boundary")
        if not pcm or len(pcm) % 2:
            raise RuntimeError("Realtime output boundary returned malformed PCM")
        bridge.on_playout_pcm(pcm, rate)
        forwarded += len(pcm)


def turn_diagnostics(metrics: dict) -> dict:
    """Safe, transcript-free event evidence for an owner preflight rerun."""
    return {
        key: metrics.get(key)
        for key in (
            "speech_started", "speech_stopped", "committed_turns",
            "speech_started_after_input_ms", "speech_stopped_after_input_ms", "committed_after_input_ms",
        )
    }


def controlled_failure_probe(tool_runtime) -> dict:
    class FailingTransport:
        async def connect(self):
            raise ConnectionError("simulated")
        async def send(self, event):
            raise AssertionError("send after failed connect")
        async def recv(self):
            raise AssertionError("recv after failed connect")
        async def close(self):
            return None

    bridge = RealtimeVoiceBridge(
        "preflight-controlled-failure",
        tool_runtime,
        transport_factory=FailingTransport,
        timeouts=RealtimeTimeouts(connect=0.25, first_response=0.25, tool=0.25, response=0.25),
    )
    started = time.perf_counter()
    bounded = False
    try:
        bridge.start()
    except RuntimeError as exc:
        bounded = isinstance(exc.__cause__, ConnectionError)
    finally:
        bridge.close()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {"bounded": bounded and elapsed_ms < 2_000, "elapsed_ms": elapsed_ms, "cleaned": not bridge.thread_alive()}


def new_bridge(session_id: str, tool_runtime) -> RealtimeVoiceBridge:
    return RealtimeVoiceBridge(
        session_id,
        tool_runtime,
        model=REALTIME_MODEL,
        timeouts=RealtimeTimeouts(connect=10, first_response=12, tool=5, response=30),
        playback_tail_ms=600,
    )


def main() -> int:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available in this terminal")
    horus_root = os.environ.get("HORUS_ROOT", "D:/HORUS/horus-core")
    horus = LocalHorusPythonPort(horus_root, enable_conversation=False)
    fixture = synthesize_fixture_48k()
    failure = controlled_failure_probe(horus)
    session_id = "realtime-preflight-primary"
    horus.resume_session(session_id)
    bridge = new_bridge(session_id, horus)
    first_output_bytes = 0
    second_output_bytes = 0
    noise_echo_frames = 0
    try:
        bridge.start()
        stream_realtime(bridge, fixture)
        wait_until(lambda: bridge.snapshot()["committed_turns"] >= 1, 20, "semantic VAD commit")
        wait_until(lambda: bridge.snapshot()["audio_output_bytes_24k"] > 0, 35, "first response audio")
        noise = b"\x01\x00" * 960
        for _ in range(20):
            bridge.on_pcm(noise, 48_000)
            noise_echo_frames += 1
            time.sleep(0.02)
        noisy = bridge.snapshot()
        if noisy["committed_turns"] != 1 or noisy["inbound_suppressed_processing_frames"] < noise_echo_frames:
            raise RuntimeError("response-playback noise created an overlapping Realtime turn")
        wait_until(lambda: bridge.snapshot()["responses_completed"] >= 1, 35, "Arabic response completion")
        initial = bridge.snapshot()
        if initial["committed_turns"] != 1:
            raise RuntimeError("semantic VAD did not commit exactly one Arabic user turn")
        if not bridge.transcript_contains("حورس"):
            raise RuntimeError("Realtime response did not semantically identify as HORUS")
        first_output_bytes = drain_output_to_playout(bridge)
        if first_output_bytes <= 0:
            raise RuntimeError("Realtime output queue received no PCM")
        wait_until(lambda: not bridge.snapshot()["turn_locked"], 5, "first turn playback drain")

        stream_realtime(bridge, fixture)
        wait_until(lambda: bridge.snapshot()["committed_turns"] == 2, 20, "second semantic VAD commit")
        wait_until(lambda: bridge.snapshot()["responses_completed"] >= 2, 35, "second Arabic response completion")
        second_output_bytes = drain_output_to_playout(bridge)
        if second_output_bytes <= 0:
            raise RuntimeError("second Realtime turn produced no 48 kHz output")
        wait_until(lambda: not bridge.snapshot()["turn_locked"], 5, "second turn playback drain")

        bridge.request_status_tool()
        wait_until(lambda: bridge.snapshot()["tool_results"] >= 1, 10, "HORUS tool result")
        continuation_base = bridge.snapshot()["responses_completed"]
        wait_until(lambda: bridge.snapshot()["responses_completed"] > continuation_base, 35, "tool continuation")
        tool = bridge.tool_result_summary()
        expected_tasks = len(horus.tasks.active_tasks())
        if tool != {"category": "status", "service": "HORUS", "ready": True, "active_tasks": expected_tasks}:
            raise RuntimeError("Realtime tool result did not match local HORUS status")
        metrics = bridge.snapshot()
    except Exception as exc:
        print(json.dumps({
            "passed": False,
            "failure_type": type(exc).__name__,
            "turn_detection": turn_diagnostics(bridge.snapshot()),
        }, ensure_ascii=False, sort_keys=True))
        raise
    finally:
        bridge.close()
        horus.close(session_id)
    primary_clean = not bridge.thread_alive() and bridge.snapshot()["closed"]

    fresh_id = "realtime-preflight-fresh"
    horus.resume_session(fresh_id)
    fresh = new_bridge(fresh_id, horus)
    try:
        fresh.start()
        fresh_ready = bool(fresh.snapshot()["session_ready"])
        fresh_connect_ms = fresh.snapshot()["connect_ms"]
    finally:
        fresh.close()
        horus.close(fresh_id)
    fresh_clean = not fresh.thread_alive() and fresh.snapshot()["closed"]

    try:
        wait_until(
            lambda: not any(t.name.startswith("horus-realtime-") for t in threading.enumerate()),
            2.0,
            "Realtime worker cleanup",
        )
    except TimeoutError:
        pass
    leaked = [thread.name for thread in threading.enumerate() if thread.name.startswith("horus-realtime-")]
    report = {
        "passed": all([
            metrics["session_ready"],
            metrics["committed_turns"] == 2,
            metrics["responses_completed"] >= 3,
            metrics["audio_input_bytes_24k"] > 0,
            metrics["audio_output_bytes_24k"] > 0,
            first_output_bytes > 0,
            second_output_bytes > 0,
            metrics["inbound_suppressed_processing_frames"] >= noise_echo_frames,
            metrics["tool_results"] == 1,
            failure["bounded"], failure["cleaned"], primary_clean,
            fresh_ready, fresh_clean, not leaked,
        ]),
        "model": REALTIME_MODEL,
        "auth_connection": True,
        "session_ready": True,
        "arabic_fixture_48k_bytes": len(fixture),
        "semantic_turns_committed": metrics["committed_turns"],
        "turn_detection": turn_diagnostics(metrics),
        "noise_echo_regression": {
            "injected_frames": noise_echo_frames,
            "suppressed_processing_frames": metrics["inbound_suppressed_processing_frames"],
            "second_turn_output_48k_bytes": second_output_bytes,
        },
        "semantic_identity_contains_horus": True,
        "realtime_audio_24k_bytes": metrics["audio_output_bytes_24k"],
        "output_boundary_48k_bytes": first_output_bytes,
        "tool_round_trip": tool,
        "controlled_failure": failure,
        "cleanup": {"primary": primary_clean, "fresh_session": fresh_clean, "background_threads": len(leaked)},
        "latency_ms": {
            "connection_session_setup": metrics["connect_ms"],
            "user_turn_end_to_first_audio": metrics["turn_to_first_audio_ms"],
            "tool_call_round_trip": metrics["tool_round_trip_ms"],
            "full_response_completion": metrics["response_completion_ms"],
            "fresh_connection_session_setup": fresh_connect_ms,
        },
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
