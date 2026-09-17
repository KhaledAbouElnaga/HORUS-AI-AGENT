"""Explicit adapter from the local voice loop to the real HORUS runtime.

The repository contains the M4 voice engine, while the deployed HORUS runtime
currently lives outside this repository behind a Telegram-only Worker entry
point.  This module therefore exposes a strict port: production code must
provide a real transport; tests use an explicitly named recording transport.
No runtime, memory, or tool behavior is silently simulated by the adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, Protocol


class RuntimeUnavailable(RuntimeError):
    """Raised when the real HORUS runtime port has not been configured."""


class RuntimeCancelled(RuntimeError):
    """Raised when a turn is cancelled before all output is consumed."""


class RuntimePort(Protocol):
    def resume_session(self, session_id: str) -> None: ...
    def stream_turn(self, session_id: str, text: str, cancel: object) -> Iterable[str]: ...
    def search_memory(self, session_id: str, query: str) -> list[dict]: ...
    def write_memory(self, session_id: str, fact: str) -> dict: ...
    def invoke_tool(self, session_id: str, category: str, arguments: dict) -> object: ...
    def cancel(self, session_id: str) -> None: ...


class ToolSafetyPort(Protocol):
    def allowed(self, category: str, arguments: dict) -> bool: ...


@dataclass(frozen=True)
class ToolDecision:
    category: str
    allowed: bool
    reason: str


@dataclass
class RuntimeSession:
    session_id: str
    context: list[dict[str, str]] = field(default_factory=list)
    turns: int = 0
    generation: int = 0
    cancelled: bool = False


@dataclass(frozen=True)
class TurnResult:
    session_id: str
    transcript: str
    output: str
    memory_hits: tuple[dict, ...]
    tool_decision: ToolDecision | None = None


class DenyByDefaultSafety:
    """Allow only read-only categories explicitly registered by the runtime."""

    def __init__(self, read_only_categories: Iterable[str] = ()):
        self._read_only = frozenset(read_only_categories)

    def allowed(self, category: str, arguments: dict) -> bool:
        return category in self._read_only


class UnconfiguredRuntime:
    """Fail-closed port used until a real HORUS transport is supplied."""

    def __getattr__(self, name):
        raise RuntimeUnavailable(f"real HORUS runtime port is not configured: {name}")


class VoiceRuntimeAdapter:
    """Lifecycle, memory, tool-safety, and cancellation coordinator.

    The adapter owns session identity and stale-output rejection.  It delegates
    actual LLM, KV/memory, and tool work to ``RuntimePort`` without inventing a
    local replacement for those capabilities.
    """

    def __init__(self, runtime: RuntimePort | None = None, safety: ToolSafetyPort | None = None):
        self.runtime = runtime or UnconfiguredRuntime()
        self.safety = safety or DenyByDefaultSafety()
        self.sessions: dict[str, RuntimeSession] = {}

    def open_session(self, session_id: str) -> RuntimeSession:
        if not session_id or session_id in self.sessions:
            raise ValueError("session_id must be non-empty and unique")
        self.runtime.resume_session(session_id)
        session = RuntimeSession(session_id=session_id)
        self.sessions[session_id] = session
        return session

    def session(self, session_id: str) -> RuntimeSession:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise RuntimeUnavailable(f"unknown local session: {session_id}") from exc

    def cancel(self, session_id: str) -> None:
        session = self.session(session_id)
        session.generation += 1
        session.cancelled = True
        self.runtime.cancel(session_id)

    def stream_turn(self, session_id: str, transcript: str) -> Iterator[str]:
        session = self.session(session_id)
        if not transcript.strip():
            raise ValueError("transcript must not be empty")
        session.generation += 1
        generation = session.generation
        session.cancelled = False
        session.context.append({"role": "user", "content": transcript})
        session.turns += 1
        for token in self.runtime.stream_turn(session_id, transcript, session):
            if session.cancelled or generation != session.generation:
                raise RuntimeCancelled(f"stale output rejected for session {session_id}")
            yield token

    def lookup_memory(self, session_id: str, query: str) -> list[dict]:
        self.session(session_id)
        if not query.strip():
            raise ValueError("memory query must not be empty")
        return self.runtime.search_memory(session_id, query)

    def write_memory(self, session_id: str, fact: str) -> dict:
        self.session(session_id)
        if not fact.strip():
            raise ValueError("memory fact must not be empty")
        return self.runtime.write_memory(session_id, fact)

    def call_tool(self, session_id: str, category: str, arguments: dict) -> object:
        self.session(session_id)
        if not self.safety.allowed(category, arguments):
            raise PermissionError(f"tool denied by fail-closed policy: {category}")
        return self.runtime.invoke_tool(session_id, category, arguments)
