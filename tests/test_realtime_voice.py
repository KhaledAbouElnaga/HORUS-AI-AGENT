import asyncio
import base64
import json
import threading
import time

import pytest

from horus_local_voice.realtime_voice import RealtimeTimeouts, RealtimeVoiceBridge


class FakeRealtimeTransport:
    def __init__(self):
        self.events = asyncio.Queue()
        self.sent = []
        self.closed = False
        self.connected = False

    async def connect(self):
        self.connected = True
        await self.events.put({"type": "session.created"})

    async def send(self, event):
        self.sent.append(event)
        if event["type"] == "session.update":
            await self.events.put({"type": "session.updated"})

    async def recv(self):
        return await self.events.get()

    async def close(self):
        self.closed = True

    async def emit(self, event):
        await self.events.put(event)


class SafeTools:
    realtime_tool_categories = frozenset({"status"})

    def __init__(self):
        self.calls = []

    def invoke_realtime_tool(self, session_id, category, arguments):
        self.calls.append((session_id, category, arguments))
        return {"service": "HORUS", "ready": True, "active_tasks": 0}


class BlockingTools(SafeTools):
    def invoke_realtime_tool(self, session_id, category, arguments):
        time.sleep(1)
        return super().invoke_realtime_tool(session_id, category, arguments)


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def make_bridge(transport=None, tools=None, events=None, **kwargs):
    transport = transport or FakeRealtimeTransport()
    tools = tools or SafeTools()
    events = events if events is not None else []
    bridge = RealtimeVoiceBridge(
        session_id="call-session",
        tool_runtime=tools,
        transport_factory=lambda: transport,
        stage_logger=lambda stage, metrics: events.append((stage, metrics)),
        timeouts=kwargs.pop("timeouts", RealtimeTimeouts(connect=1, first_response=1, tool=1, response=1)),
        **kwargs,
    )
    bridge.start()
    return bridge, transport, tools, events


def emit(bridge, transport, event):
    asyncio.run_coroutine_threadsafe(transport.emit(event), bridge.loop).result(1)


def test_realtime_session_uses_pcm24_semantic_vad_horus_identity_and_safe_tools():
    bridge, transport, _tools, _events = make_bridge()
    update = next(item for item in transport.sent if item["type"] == "session.update")
    session = update["session"]
    assert session["model"] == "gpt-realtime-2.1"
    assert session["output_modalities"] == ["audio"]
    assert session["audio"]["input"]["format"] == {"type": "audio/pcm", "rate": 24_000}
    assert session["audio"]["input"]["turn_detection"] == {
        "type": "semantic_vad", "eagerness": "medium", "create_response": True, "interrupt_response": False,
    }
    assert session["audio"]["output"]["format"] == {"type": "audio/pcm", "rate": 24_000}
    assert "حورس" in session["instructions"] and "Khaled" in session["instructions"]
    assert [tool["name"] for tool in session["tools"]] == ["get_horus_status"]
    bridge.request_status_tool()
    assert wait_until(lambda: any(
        item.get("type") == "response.create" and item.get("response", {}).get("tool_choice") == "required"
        for item in transport.sent
    ))
    bridge.close()


def test_realtime_exact_audio_path_downsamples_input_and_upsamples_output_to_existing_boundary():
    bridge, transport, _tools, events = make_bridge()
    pcm48 = b"\x01\x00\x02\x00" * 480  # 20 ms, mono PCM16 at 48 kHz
    bridge.on_pcm(pcm48, 48_000)
    assert wait_until(lambda: any(item["type"] == "input_audio_buffer.append" for item in transport.sent))
    append = next(item for item in transport.sent if item["type"] == "input_audio_buffer.append")
    pcm24 = base64.b64decode(append["audio"])
    assert 0 < len(pcm24) <= len(pcm48)

    model_pcm24 = b"\x11\x00" * 480
    emit(bridge, transport, {"type": "response.created", "response": {"id": "r1"}})
    emit(bridge, transport, {"type": "response.output_audio.delta", "response_id": "r1", "delta": base64.b64encode(model_pcm24).decode()})
    assert wait_until(lambda: bridge.output.qsize() == 1)
    pcm_out, rate = bridge.next_output(timeout=0.2)
    assert rate == 48_000 and len(pcm_out) >= len(model_pcm24) and any(pcm_out)
    assert any(stage == "realtime_audio_forwarded" for stage, _ in events)
    bridge.close()


def test_realtime_turn_commit_transcript_semantics_and_response_metrics_are_in_memory_only():
    bridge, transport, _tools, events = make_bridge()
    emit(bridge, transport, {"type": "input_audio_buffer.speech_stopped", "item_id": "u1"})
    emit(bridge, transport, {"type": "input_audio_buffer.committed", "item_id": "u1"})
    emit(bridge, transport, {"type": "response.created", "response": {"id": "r1"}})
    emit(bridge, transport, {"type": "response.output_audio_transcript.done", "response_id": "r1", "transcript": "أنا حورس"})
    emit(bridge, transport, {"type": "response.done", "response": {"id": "r1", "status": "completed"}})
    assert wait_until(lambda: bridge.snapshot()["responses_completed"] == 1)
    snap = bridge.snapshot()
    assert snap["committed_turns"] == 1
    assert bridge.transcript_contains("حورس")
    assert snap["response_completion_ms"] is not None
    assert all("حورس" not in json.dumps(metrics, ensure_ascii=False) for _, metrics in events)
    bridge.close()


def test_realtime_tool_round_trip_executes_local_safe_tool_and_continues_same_session():
    bridge, transport, tools, events = make_bridge()
    emit(bridge, transport, {
        "type": "response.output_item.done",
        "item": {"type": "function_call", "name": "get_horus_status", "call_id": "tool-1", "arguments": "{}"},
    })
    assert wait_until(lambda: bool(tools.calls))
    assert tools.calls == [("call-session", "status", {})]
    output = next(item for item in transport.sent if item["type"] == "conversation.item.create")
    assert output["item"]["type"] == "function_call_output"
    assert output["item"]["call_id"] == "tool-1"
    assert json.loads(output["item"]["output"])["service"] == "HORUS"
    assert any(item["type"] == "response.create" for item in transport.sent)
    assert any(stage == "realtime_tool_call" for stage, _ in events)
    assert any(stage == "realtime_tool_result" for stage, _ in events)
    bridge.close()


def test_failed_response_requests_bounded_arabic_fallback_without_counting_completion():
    bridge, transport, _tools, events = make_bridge()
    emit(bridge, transport, {"type": "response.created", "response": {"id": "failed"}})
    emit(bridge, transport, {"type": "response.done", "response": {"id": "failed", "status": "failed"}})
    assert wait_until(lambda: any(
        item.get("type") == "response.create" and "حصل عطل مؤقت" in item.get("response", {}).get("instructions", "")
        for item in transport.sent
    ))
    assert bridge.snapshot()["responses_completed"] == 0
    assert any(stage == "realtime_error" for stage, _ in events)
    bridge.close()



def test_realtime_tool_timeout_is_bounded_requests_controlled_fallback_and_cleans_up():
    timeouts = RealtimeTimeouts(connect=1, first_response=1, tool=0.05, response=1)
    bridge, transport, _tools, events = make_bridge(tools=BlockingTools(), timeouts=timeouts)
    emit(bridge, transport, {
        "type": "response.output_item.done",
        "item": {"type": "function_call", "name": "get_horus_status", "call_id": "tool-timeout", "arguments": "{}"},
    })
    assert wait_until(lambda: any(stage == "realtime_timeout" for stage, _ in events))
    fallback = [item for item in transport.sent if item["type"] == "response.create"]
    assert fallback and "حصل عطل مؤقت" in fallback[-1]["response"]["instructions"]
    bridge.close()
    assert transport.closed and not bridge.thread_alive()


def test_realtime_close_clears_tasks_and_fresh_session_starts_cleanly():
    first_transport = FakeRealtimeTransport()
    first, _, _, _ = make_bridge(transport=first_transport)
    first.close()
    assert first_transport.closed and not first.thread_alive() and first.snapshot()["closed"]

    second_transport = FakeRealtimeTransport()
    second, _, _, _ = make_bridge(transport=second_transport)
    assert second_transport.connected and second.snapshot()["session_ready"]
    second.close()


def test_realtime_rejects_non_48k_input_without_local_vad_or_legacy_components():
    bridge, _transport, _tools, _events = make_bridge()
    with pytest.raises(ValueError, match="48 kHz"):
        bridge.on_pcm(b"\x00\x00", 16_000)
    assert not hasattr(bridge, "endpoint")
    assert not hasattr(bridge, "processor")
    bridge.close()
