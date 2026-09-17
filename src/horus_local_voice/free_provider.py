"""Bridge HORUS to Hermes' already-verified keyless OpenCode execution path.

Do not call the Zen HTTP endpoint from here.  OpenCode Free rejects direct API
clients ("can only be used from within OpenCode").  Hermes' ``oneshot`` runner
is the local path that actually worked: it constructs the normal AIAgent,
resolves ``opencode-free`` through Hermes, and owns the provider headers and
session database.
"""
from __future__ import annotations

import asyncio
import importlib
import os
from pathlib import Path
import sys
from typing import Any, Callable


FREE_PROVIDER = "opencode-free"
FREE_MODELS = ("nemotron-3-ultra-free", "nemotron-3.5-lightning-free")


def _hermes_root() -> Path:
    configured = os.environ.get("HERMES_AGENT_ROOT", "").strip()
    if configured:
        return Path(configured)
    return Path.home() / "AppData" / "Local" / "hermes" / "hermes-agent"


def _load_runner() -> Callable[..., tuple[str, dict[str, Any]]]:
    root = _hermes_root()
    if not (root / "hermes_cli" / "oneshot.py").is_file():
        raise RuntimeError(f"Hermes agent runtime not found: {root}")
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    try:
        return importlib.import_module("hermes_cli.oneshot")._run_agent
    except Exception as exc:  # pragma: no cover - environment-specific diagnostic
        raise RuntimeError("could not load Hermes one-shot runner") from exc


def _messages_to_prompt(messages: list[dict]) -> str:
    """Preserve HORUS' system prompt, memory context, and turn history for Hermes."""
    rendered = []
    for message in messages:
        role = str(message.get("role") or "message").upper()
        content = message.get("content") or ""
        if isinstance(content, list):
            content = " ".join(str(part.get("text") or "") for part in content if isinstance(part, dict))
        rendered.append(f"[{role}]\n{content}")
    return "\n\n".join(rendered)


class HermesFreeProvider:
    """Completion through Hermes' local AIAgent/OpenCode Free path."""

    def __init__(self, runner: Callable[..., tuple[str, dict[str, Any]]] | None = None):
        self._runner = runner or _load_runner()
        self._hermes_sessions: dict[str, str] = {}
        self._bound_session: str | None = None

    def bind_session(self, session_id: str | None) -> None:
        self._bound_session = session_id

    def close_session(self, session_id: str) -> None:
        self._hermes_sessions.pop(session_id, None)
        if self._bound_session == session_id:
            self._bound_session = None

    async def complete(self, messages: list[dict], model_tier: str = "fast") -> tuple[str, str, float]:
        del model_tier  # The voice contract deliberately uses the verified two-model chain.
        last_error: Exception | None = None
        horus_session = self._bound_session
        resume = self._hermes_sessions.get(horus_session) if horus_session else None
        prompt = _messages_to_prompt(messages)
        for model in FREE_MODELS:
            try:
                response, result = await asyncio.to_thread(
                    self._runner,
                    prompt,
                    model=model,
                    provider=FREE_PROVIDER,
                    use_config_toolsets=False,
                    resume=resume,
                )
                text = str(response or "").strip()
                if not text:
                    raise RuntimeError(f"Hermes returned an empty response for {model}")
                if horus_session and result.get("session_id"):
                    self._hermes_sessions[horus_session] = str(result["session_id"])
                return text, model, 0.0
            except Exception as exc:  # noqa: BLE001 - provider failover boundary
                last_error = exc
        raise RuntimeError(
            "all Hermes OpenCode Free models failed: "
            f"{type(last_error).__name__ if last_error else 'unresolved'}"
        ) from last_error


def install_free_provider(router_module: Any, provider: HermesFreeProvider | None = None) -> HermesFreeProvider:
    """Replace only HORUS' completion seam; keep agent, memory, tools, and sessions intact."""
    current = getattr(router_module, "_horus_free_provider", None)
    if current is not None:
        return current
    bridge = provider or HermesFreeProvider()
    router_module.complete = bridge.complete
    router_module._horus_free_provider = bridge
    return bridge


__all__ = ["FREE_MODELS", "FREE_PROVIDER", "HermesFreeProvider", "install_free_provider"]
