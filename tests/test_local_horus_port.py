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
    adapter, _port, sid = local_runtime
    for category in ("status", "tasks", "cost"):
        result = adapter.call_tool(sid, category, {})
        assert result["category"] == category
    with pytest.raises(PermissionError):
        adapter.call_tool(sid, "delete", {})


def test_real_local_horus_memory_intent_runs_through_voice_turn(local_runtime):
    adapter, _port, sid = local_runtime
    list(adapter.stream_turn(sid, "remember the location is Cairo"))
    list(adapter.stream_turn(sid, "remember the location is Giza"))
    assert "Giza" in "".join(adapter.stream_turn(sid, "what is my location"))


def test_real_local_horus_command_turn_uses_agent_loop(local_runtime):
    adapter, port, sid = local_runtime
    assert port.native_streaming is False
    assert "شغال" in "".join(adapter.stream_turn(sid, "/status"))


def test_runtime_transport_chunks_preserve_response_whitespace(local_runtime):
    adapter, port, sid = local_runtime
    import asyncio
    expected, _model, _cost = asyncio.run(port.agent.handle_text("/status"))
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
