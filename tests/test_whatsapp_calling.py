from horus_local_voice.whatsapp_calling import SimulatedWhatsAppCallingReplay, WhatsAppCallingAdapter


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def open_session(self, session_id): self.calls.append(("open", session_id))
    def ingest_media(self, session_id, media): self.calls.append(("media", session_id, media))
    def cancel(self, session_id): self.calls.append(("cancel", session_id))
    def close_session(self, session_id): self.calls.append(("close", session_id))


def envelope(event_id, kind, **extra):
    return {"event_id": event_id, "kind": kind, "call_id": "call-1", "user_id": "user-1", "phone_number_id": "phone-1", **extra}


def test_simulated_call_lifecycle_correlates_and_tears_down():
    runtime = FakeRuntime(); adapter = WhatsAppCallingAdapter(runtime)
    rows = SimulatedWhatsAppCallingReplay(adapter).run([
        envelope("e1", "incoming"), envelope("e2", "connected"),
        envelope("e3", "media", media=b"pcm"), envelope("e4", "hangup"),
    ])
    assert [row["status"] for row in rows] == ["accepted"] * 4
    assert all(row["evidence"] == "SIMULATED" for row in rows)
    sid = "wa:phone-1:user-1:call-1"
    assert runtime.calls == [("open", sid), ("media", sid, b"pcm"), ("cancel", sid), ("close", sid)]


def test_duplicate_control_event_is_idempotent_and_redacted():
    runtime = FakeRuntime(); adapter = WhatsAppCallingAdapter(runtime)
    first = adapter.ingest(envelope("same", "incoming"))
    duplicate = adapter.ingest(envelope("same", "incoming"))
    assert first["status"] == "accepted"
    assert duplicate["status"] == "duplicate"
    assert adapter.duplicate_events == 1
    observed = adapter.observe(__import__("horus_local_voice.whatsapp_calling", fromlist=["CallingEvent"]).CallingEvent.from_envelope(envelope("x", "connected")))
    assert observed == {"kind": "connected", "event_id": "[REDACTED]", "media_bytes": 0}


def test_media_before_connect_and_mismatched_lifecycle_fail_closed():
    runtime = FakeRuntime(); adapter = WhatsAppCallingAdapter(runtime)
    row = adapter.ingest(envelope("e1", "media", media=b"x"))
    assert row["status"] == "stale"
    assert runtime.calls == []
    bad = dict(envelope("e2", "incoming")); bad.pop("user_id")
    try:
        adapter.ingest(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed envelope was accepted")
