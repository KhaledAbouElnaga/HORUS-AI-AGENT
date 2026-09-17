"""Run reproducible evidence against the installed local HORUS Python core."""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from horus_local_voice.local_horus_port import LocalHorusPythonPort
from horus_local_voice.runtime_adapter import DenyByDefaultSafety, VoiceRuntimeAdapter


def main() -> None:
    port = LocalHorusPythonPort()
    adapter = VoiceRuntimeAdapter(port, DenyByDefaultSafety(port.tool_categories))
    first = f"m5-evidence-{uuid.uuid4().hex}"
    second = f"m5-isolated-{uuid.uuid4().hex}"
    adapter.open_session(first)
    adapter.open_session(second)
    try:
        for fact in ("name=Khaled", "city=Cairo", "role=owner"):
            adapter.write_memory(first, fact)
        adapter.write_memory(first, "city=Giza")
        recalled = adapter.lookup_memory(first, "city")
        isolated = adapter.lookup_memory(second, "city")
        tools = {name: adapter.call_tool(first, name, {}) for name in sorted(port.tool_categories)}
        forgotten = asyncio.run(port.memory.forget(f"{first}:city"))
        after_forget = adapter.lookup_memory(first, "city")
        status_words = list(adapter.stream_turn(first, "/status"))
        print(json.dumps({
            "runtime": "D:/HORUS/horus-core/app",
            "sessions": 2,
            "facts_introduced": 3,
            "correction": recalled[-1]["value"] == "Giza",
            "late_recall": [row["value"] for row in recalled],
            "cross_session_isolation": isolated == [],
            "forget_supported": forgotten and after_forget == [],
            "tools": sorted(tools),
            "status_turn": " ".join(status_words),
            "native_streaming": port.native_streaming,
        }, ensure_ascii=False, indent=2))
    finally:
        for key in ("name", "city", "role"):
            asyncio.run(port.memory.forget(f"{first}:{key}"))


if __name__ == "__main__":
    main()
