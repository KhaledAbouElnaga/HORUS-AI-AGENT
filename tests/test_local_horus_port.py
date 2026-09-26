import uuid

import pytest

from horus_local_voice.local_horus_port import LocalHorusPythonPort
from horus_local_voice.runtime_adapter import DenyByDefaultSafety, VoiceRuntimeAdapter


@pytest.fixture
def local_runtime():
    port = LocalHorusPythonPort()
    adapter = VoiceRuntimeAdapter(port, DenyByDefaultSafety(port.tool_categories))
    sid = f"test-{uuid.uuid4().hex}"
    adapter.open_session(sid)
    yield adapter, port, sid
    for key in ["name", "city", "role"]:
        import asyncio
        asyncio.run(port.memory.forget(f"{sid}:{key}"))


def test_real_local_horus_memory_update_and_isolation(local_runtime):
    adapter, _port, sid = local_runtime
    other = f"other-{uuid.uuid4().hex}"
    adapter.open_session(other)
    adapter.write_memory(sid, "name=Khaled")
    adapter.write_memory(sid, "city=Cairo")
    adapter.write_memory(sid, "role=owner")
    adapter.write_memory(sid, "city=Giza")
    assert adapter.lookup_memory(sid, "city")[-1]["value"] == "Giza"
    assert adapter.lookup_memory(other, "city") == []


def test_real_local_horus_safe_tool_categories_and_mutation_deny(local_runtime):
    adapter, port, sid = local_runtime
    port.free_provider._runner = lambda prompt, **kwargs: ("tool response", {"session_id": "s"})
    for category in ("status", "tasks", "cost"):
        result = adapter.call_tool(sid, category, {})
        assert result["category"] == category
    with pytest.raises(PermissionError):
        adapter.call_tool(sid, "delete", {})


def test_realtime_readonly_status_tool_bypasses_conversational_provider(local_runtime):
    _adapter, port, sid = local_runtime
    port.free_provider._runner = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider must not run"))
    result = port.invoke_realtime_tool(sid, "status", {})
    assert result["service"] == "HORUS"
    assert result["ready"] is True
    assert result["active_tasks"] == len(port.tasks.active_tasks())
    with pytest.raises(PermissionError):
        port.invoke_realtime_tool(sid, "delete", {})


def test_real_local_horus_memory_intent_runs_through_voice_turn(local_runtime):
    adapter, _port, sid = local_runtime
    list(adapter.stream_turn(sid, "remember the location is Cairo"))
    list(adapter.stream_turn(sid, "remember the location is Giza"))
    assert "Giza" in "".join(adapter.stream_turn(sid, "what is my location"))


def test_real_local_horus_command_turn_uses_agent_loop(local_runtime):
    adapter, port, sid = local_runtime
    port.free_provider._runner = lambda prompt, **kwargs: ("شغال", {"session_id": "s"})
    assert port.native_streaming is False
    assert "شغال" in "".join(adapter.stream_turn(sid, "/status"))


def test_runtime_transport_chunks_preserve_response_whitespace(local_runtime):
    adapter, port, sid = local_runtime
    expected = "response with spaces"
    port.free_provider._runner = lambda prompt, **kwargs: (expected, {"session_id": "s"})
    assert "".join(adapter.stream_turn(sid, "/status")) == expected


def test_stt_to_horus_free_provider_to_response(local_runtime):
    adapter, port, sid = local_runtime
    calls = []

    def runner(prompt, **kwargs):
        calls.append(kwargs)
        return "HORUS voice response", {"session_id": "hermes-voice-session"}

    port.free_provider._runner = runner
    assert "HORUS voice response" == "".join(adapter.stream_turn(sid, "transcribed speech"))
    assert calls[0]["provider"] == "opencode-free"
    assert calls[0]["model"] == "nemotron-3-ultra-free"


def test_voice_port_does_not_import_hermes_agent_modules():
    port = LocalHorusPythonPort()
    assert port.agent is None
    assert port.free_provider._runner is not None


def test_hermes_runtime_failure_is_controlled_and_voice_port_recovers(local_runtime):
    adapter, port, sid = local_runtime
    calls = {"count": 0}

    def runner(prompt, **kwargs):
        calls["count"] += 1
        if calls["count"] <= 2:
            raise RuntimeError("simulated Hermes runtime failure")
        return "recovered response", {"session_id": "s"}

    port.free_provider._runner = runner
    with pytest.raises(RuntimeError, match="all Hermes OpenCode Free models failed"):
        list(adapter.stream_turn(sid, "first turn"))
    assert "recovered response" == "".join(adapter.stream_turn(sid, "second turn"))
