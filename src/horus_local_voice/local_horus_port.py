"""Process-safe transport to the existing local HORUS memory and task modules."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Iterable

from .runtime_adapter import RuntimeCancelled
from .free_provider import HermesFreeProvider


class LocalHorusPythonPort:
    """Voice port; Hermes agent execution stays in its own Python process."""

    native_streaming = False
    tool_categories = frozenset({"status", "tasks", "cost"})

    def __init__(self, root: str | Path = "D:/HORUS/horus-core"):
        self.root = Path(root)
        if not (self.root / "app/core/agent.py").is_file():
            raise FileNotFoundError(f"HORUS core not found: {self.root}")
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        # These modules are deliberately narrow and do not import Hermes' agent.
        from app.adapters.memory import store  # noqa: PLC0415
        from app.tasks import engine  # noqa: PLC0415
        self.free_provider = HermesFreeProvider()
        self.agent, self.voice_state = None, None
        self.memory, self.tasks = store, engine
        self._cancelled: set[str] = set()
        self._contexts: dict[str, list[dict]] = {}
        self.last_turn_metrics: dict[str, float | bool] = {"hermes_rpc_elapsed_ms": 0.0, "session_reused": False}

    def resume_session(self, session_id: str) -> None:
        self._contexts.setdefault(session_id, [])
        self._cancelled.discard(session_id)

    def stream_turn(self, session_id: str, text: str, cancel: object) -> Iterable[str]:
        if session_id in self._cancelled:
            raise RuntimeCancelled(f"cancelled before HORUS turn: {session_id}")
        context = self._contexts.setdefault(session_id, [])
        normalized = self.normalize_spoken_command(text)
        memory_reply = self._memory_intent(session_id, text)
        if memory_reply is not None:
            self.last_turn_metrics = {"hermes_rpc_elapsed_ms": 0.0, "session_reused": False}
            reply, model, cost = memory_reply, "local-memory", 0.0
        else:
            self.free_provider.bind_session(session_id)
            messages = context + [{"role": "user", "content": normalized}]
            reply, model, cost = asyncio.run(self.free_provider.complete(messages))
            self.last_turn_metrics = self.free_provider.last_completion_metrics.copy()
        context.extend([{"role": "user", "content": text}, {"role": "assistant", "content": reply}])
        yield from re.findall(r"\S+\s*", reply)

    @staticmethod
    def normalize_spoken_command(text: str) -> str:
        value = " ".join(text.lower().split())
        if value.startswith("/status") or any(x in value for x in ("status", "health", "healthy", "system", "doing", "حالة", "صحتك", "صحّتك", "حالة النظام")):
            return "/status"
        if value.startswith("/tasks") or any(x in value for x in ("tasks", "active work", "active task", "act of work", "work", "المهام", "المهم", "مهام")):
            return "/tasks"
        if value.startswith("/cost") or any(x in value for x in ("cost", "expense", "expenses", "التكلفة", "التكلفه", "التقليفة", "التقليفه", "التطلفة")):
            return "/cost"
        return text

    def _memory_intent(self, session_id: str, text: str) -> str | None:
        value = re.sub(r"[.!?؟]+$", "", " ".join(text.strip().split()))
        match = re.match(r"(?:please\s+)?(?:remember|save memory)[,\s]+(?:the\s+)?([A-Za-z][\w-]*)[,\s]+(?:is|=|equals)?\s*(.+)", value, re.I)
        if match:
            self.write_memory(session_id, f"{match.group(1)}={match.group(2)}")
            return f"Saved {match.group(1)}."
        match = re.match(r"(?:what is|recall|remember)\s+(?:my\s+)?([A-Za-z][\w-]*)\??$", value, re.I)
        if match:
            rows = self.search_memory(session_id, match.group(1))
            return f"{match.group(1)} is {rows[-1]['value']}." if rows else f"I have no saved {match.group(1)}."
        match = re.match(r"(?:forget|delete memory)\s+([A-Za-z][\w-]*)$", value, re.I)
        if match:
            asyncio.run(self.memory.forget(f"{session_id}:{match.group(1)}"))
            return f"Forgot {match.group(1)}."
        return None

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
        reply = "".join(self.stream_turn(session_id, commands[category], None))
        return {"category": category, "reply": reply, "model": "opencode-free", "cost": 0.0}

    def cancel(self, session_id: str) -> None:
        self._cancelled.add(session_id)

    def close(self, session_id: str) -> None:
        self.free_provider.close_session(session_id)
        self._contexts.pop(session_id, None)
        self._cancelled.discard(session_id)
