from __future__ import annotations

import pytest

from horus_local_voice.runtime_adapter import (
    DenyByDefaultSafety,
    RuntimeCancelled,
    VoiceRuntimeAdapter,
)


class RecordingRuntime:
    def __init__(self):
        self.resumed = []
        self.cancelled = []
        self.memory = {}
        self.tool_calls = []

    def resume_session(self, session_id):
        self.resumed.append(session_id)

    def stream_turn(self, session_id, text, cancel):
        yield f"reply:{session_id}:{text}"
        yield " second"

    def search_memory(self, session_id, query):
        return self.memory.get(session_id, [])

    def write_memory(self, session_id, fact):
        self.memory.setdefault(session_id, []).append({"fact": fact})
        return self.memory[session_id][-1]

    def invoke_tool(self, session_id, category, arguments):
        self.tool_calls.append((session_id, category, arguments))
        return {"category": category, "ok": True}

    def cancel(self, session_id):
        self.cancelled.append(session_id)


def test_real_port_is_required_instead_of_silent_local_fallback():
    adapter = VoiceRuntimeAdapter()
    with pytest.raises(RuntimeError, match="not configured"):
        adapter.open_session("s1")


def test_sessions_delegate_identity_and_isolate_memory():
    runtime = RecordingRuntime()
    adapter = VoiceRuntimeAdapter(runtime)
    adapter.open_session("s1")
    adapter.open_session("s2")

    adapter.write_memory("s1", "three facts")
    assert adapter.lookup_memory("s1", "facts") == [{"fact": "three facts"}]
    assert adapter.lookup_memory("s2", "facts") == []
    assert runtime.resumed == ["s1", "s2"]


def test_streaming_preserves_session_and_rejects_stale_tokens_after_cancel():
    runtime = RecordingRuntime()
    adapter = VoiceRuntimeAdapter(runtime)
    adapter.open_session("s1")
    tokens = adapter.stream_turn("s1", "hello")
    assert next(tokens) == "reply:s1:hello"
    adapter.cancel("s1")
    with pytest.raises(RuntimeCancelled, match="stale output"):
        next(tokens)
    assert runtime.cancelled == ["s1"]


def test_tools_are_denied_by_default_and_allowed_categories_use_real_port():
    runtime = RecordingRuntime()
    adapter = VoiceRuntimeAdapter(runtime, DenyByDefaultSafety({"weather", "wiki"}))
    adapter.open_session("s1")
    with pytest.raises(PermissionError, match="fail-closed"):
        adapter.call_tool("s1", "delete", {})
    assert adapter.call_tool("s1", "weather", {"city": "Cairo"}) == {"category": "weather", "ok": True}
    assert runtime.tool_calls == [("s1", "weather", {"city": "Cairo"})]
