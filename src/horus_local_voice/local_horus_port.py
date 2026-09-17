"""Transport to the existing local Python HORUS runtime.

This imports the real application under ``D:/HORUS/horus-core``; it does not
reimplement agent, memory, or task logic. The runtime currently returns complete
responses, so the adapter exposes word chunks but records native streaming as
unsupported instead of claiming token streaming.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Iterable

from .runtime_adapter import RuntimeCancelled


class LocalHorusPythonPort:
    """RuntimePort for the existing local FastAPI application's core modules."""

    native_streaming = False
    tool_categories = frozenset({"status", "tasks", "cost"})

    def __init__(self, root: str | Path = "D:/HORUS/horus-core"):
        self.root = Path(root)
        if not (self.root / "app/core/agent.py").is_file():
            raise FileNotFoundError(f"HORUS core not found: {self.root}")
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from app.core import agent, voice_state  # noqa: PLC0415
        from app.adapters.memory import store  # noqa: PLC0415
        from app.tasks import engine  # noqa: PLC0415
        self.agent, self.voice_state = agent, voice_state
        self.memory, self.tasks = store, engine
        self._cancelled: set[str] = set()
        self._contexts: dict[str, list[dict]] = {}

    def resume_session(self, session_id: str) -> None:
        self._contexts.setdefault(session_id, [])
        self._cancelled.discard(session_id)

    def stream_turn(self, session_id: str, text: str, cancel: object) -> Iterable[str]:
        if session_id in self._cancelled:
            raise RuntimeCancelled(f"cancelled before HORUS turn: {session_id}")
        context = self._contexts.setdefault(session_id, [])
        reply, _model, _cost = asyncio.run(self.agent.handle_text(text, context=context))
        context.extend([{"role": "user", "content": text}, {"role": "assistant", "content": reply}])
        # The real app returns one completed response; these are transport chunks,
        # not evidence that the remote/local agent emitted a native stream.
        yield from (piece for piece in reply.split() if piece)

    def search_memory(self, session_id: str, query: str) -> list[dict]:
        prefix = f"{session_id}:"
        rows = asyncio.run(self.memory.recall(f"m5:{session_id}:{query}", limit=50))
        return [row for row in rows if row.get("key", "").startswith(prefix) and (query.lower() in row.get("key", "").lower() or query.lower() in row.get("value", "").lower())]

    def write_memory(self, session_id: str, fact: str) -> dict:
        if "=" not in fact:
            raise ValueError("memory fact must use key=value")
        key, value = (part.strip() for part in fact.split("=", 1))
        asyncio.run(self.memory.remember("m5", f"{session_id}:{key}", value))
        return {"session_id": session_id, "key": key, "value": value, "persisted_by": "HORUS memory store"}

    def invoke_tool(self, session_id: str, category: str, arguments: dict) -> object:
        if category not in self.tool_categories:
            raise PermissionError(f"unsupported local HORUS tool category: {category}")
        commands = {"status": "/status", "tasks": "/tasks", "cost": "/cost"}
        reply, model, cost = asyncio.run(self.agent.handle_text(commands[category]))
        return {"category": category, "reply": reply, "model": model, "cost": cost}

    def cancel(self, session_id: str) -> None:
        self._cancelled.add(session_id)

    def close(self, session_id: str) -> None:
        self._contexts.pop(session_id, None)
        self._cancelled.discard(session_id)
