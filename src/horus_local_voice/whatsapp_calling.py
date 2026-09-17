"""Official WhatsApp Calling channel boundary and offline replay contract.

This module deliberately accepts only a normalized control/media envelope. It
contains no Graph client, token handling, SIP credentials, or private WhatsApp
protocol code. Live Meta payload details remain account/documentation gates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class CallingContractError(ValueError):
    pass


class CallingRuntime(Protocol):
    def open_session(self, session_id: str) -> object: ...
    def ingest_media(self, session_id: str, media: bytes) -> None: ...
    def cancel(self, session_id: str) -> None: ...
    def close_session(self, session_id: str) -> None: ...


@dataclass(frozen=True)
class CallingEvent:
    """Normalized fields needed by the adapter; source payload is not retained."""

    event_id: str
    kind: str
    call_id: str
    user_id: str
    phone_number_id: str
    media: bytes = b""

    @classmethod
    def from_envelope(cls, envelope: dict) -> "CallingEvent":
        required = ("event_id", "kind", "call_id", "user_id", "phone_number_id")
        missing = [key for key in required if not isinstance(envelope.get(key), str) or not envelope[key]]
        if missing:
            raise CallingContractError(f"missing required normalized fields: {','.join(missing)}")
        kind = envelope["kind"]
        if kind not in {"incoming", "connected", "media", "hangup"}:
            raise CallingContractError(f"unsupported calling event kind: {kind}")
        media = envelope.get("media", b"")
        if kind == "media" and not isinstance(media, (bytes, bytearray)):
            raise CallingContractError("media event must carry bytes at the channel boundary")
        return cls(envelope["event_id"], kind, envelope["call_id"], envelope["user_id"], envelope["phone_number_id"], bytes(media))


@dataclass
class CallSession:
    session_id: str
    call_id: str
    user_id: str
    phone_number_id: str
    state: str = "NEW"
    seen_event_ids: set[str] = field(default_factory=set)
    media_frames: int = 0
    generation: int = 0


class WhatsAppCallingAdapter:
    """Stateful, deduplicating adapter; all HORUS work is delegated."""

    def __init__(self, runtime: CallingRuntime):
        self.runtime = runtime
        self.sessions: dict[str, CallSession] = {}
        self.call_to_session: dict[str, str] = {}
        self.duplicate_events = 0
        self.stale_events = 0
        self.identity_mismatches = 0

    @staticmethod
    def session_id(event: CallingEvent) -> str:
        return f"wa:{event.phone_number_id}:{event.user_id}:{event.call_id}"

    def ingest(self, envelope: dict) -> dict:
        event = CallingEvent.from_envelope(envelope)
        sid = self.call_to_session.get(event.call_id)
        if sid is None:
            sid = self.session_id(event)
            session = self.sessions.setdefault(sid, CallSession(sid, event.call_id, event.user_id, event.phone_number_id))
            self.call_to_session[event.call_id] = sid
        else:
            session = self.sessions[sid]
            if (event.user_id, event.phone_number_id) != (session.user_id, session.phone_number_id):
                self.identity_mismatches += 1
                self.stale_events += 1
                return {"status": "contract_mismatch", "session_id": sid, "stale_output": 0}
        if event.event_id in session.seen_event_ids:
            self.duplicate_events += 1
            return {"status": "duplicate", "session_id": sid, "stale_output": 0}
        session.seen_event_ids.add(event.event_id)
        if event.kind == "incoming":
            if session.state not in {"NEW", "CLOSED"}:
                self.stale_events += 1
                return {"status": "stale", "session_id": sid, "stale_output": 0}
            self.runtime.open_session(sid)
            session.state, session.generation = "RINGING", session.generation + 1
        elif event.kind == "connected":
            if session.state != "RINGING":
                self.stale_events += 1
                return {"status": "stale", "session_id": sid, "stale_output": 0}
            session.state = "CONNECTED"
        elif event.kind == "media":
            if session.state != "CONNECTED":
                self.stale_events += 1
                return {"status": "stale", "session_id": sid, "stale_output": 0}
            self.runtime.ingest_media(sid, event.media)
            session.media_frames += 1
        elif event.kind == "hangup":
            if session.state == "CLOSED":
                self.stale_events += 1
                return {"status": "stale", "session_id": sid, "stale_output": 0}
            session.generation += 1
            self.runtime.cancel(sid)
            self.runtime.close_session(sid)
            session.state = "CLOSED"
        return {"status": "accepted", "session_id": sid, "state": session.state, "stale_output": 0}

    def observe(self, event: CallingEvent) -> dict:
        """Redacted observability; never returns phone/user/call identifiers."""
        return {"kind": event.kind, "event_id": "[REDACTED]", "media_bytes": len(event.media)}


class SimulatedWhatsAppCallingReplay:
    """Offline replay only; every result is explicitly marked SIMULATED."""

    label = "SIMULATED"

    def __init__(self, adapter: WhatsAppCallingAdapter):
        self.adapter = adapter

    def run(self, envelopes: list[dict]) -> list[dict]:
        return [{"evidence": self.label, **self.adapter.ingest(envelope)} for envelope in envelopes]
