"""Process-boundary bridge to Hermes' verified keyless OpenCode path.

The voice environment never imports Hermes. The subprocess inherits the user's
already-configured Hermes runtime environment and owns provider/session state.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable


FREE_PROVIDER = "opencode-free"
FREE_MODELS = ("nemotron-3-ultra-free", "nemotron-3.5-lightning-free")


def _hermes_root() -> Path:
    configured = os.environ.get("HERMES_AGENT_ROOT", "").strip()
    if configured:
        return Path(configured)
    return Path.home() / "AppData" / "Local" / "hermes" / "hermes-agent"


def _hermes_python() -> Path:
    configured = os.environ.get("HERMES_AGENT_PYTHON", "").strip()
    if configured:
        return Path(configured)
    root = _hermes_root()
    return root / "venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")


def _load_runner() -> Callable[..., tuple[str, dict[str, Any]]]:
    python = _hermes_python()
    rpc = Path(__file__).resolve().parents[2] / "scripts" / "hermes_free_rpc.py"
    if not python.is_file():
        raise RuntimeError(f"Hermes interpreter not found: {python}")
    if not rpc.is_file():
        raise RuntimeError(f"Hermes RPC bridge not found: {rpc}")

    def run(prompt: str, **kwargs) -> tuple[str, dict[str, Any]]:
        request = {"prompt": prompt, "model": kwargs["model"], "provider": kwargs["provider"], "resume": kwargs.get("resume")}
        child_env = os.environ.copy()
        child_env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
        completed = subprocess.run(
            [str(python), str(rpc)], input=json.dumps(request, ensure_ascii=False) + "\n",
            text=True, encoding="utf-8", errors="strict", capture_output=True, timeout=180, check=False,
            env=child_env,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Hermes subprocess failed with exit code {completed.returncode}")
        try:
            result = json.loads(completed.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as exc:
            raise RuntimeError("Hermes subprocess returned invalid RPC output") from exc
        if not result.get("ok"):
            raise RuntimeError("Hermes subprocess returned a controlled error")
        return str(result.get("response") or ""), {"session_id": result.get("session_id")}

    return run


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
        self.last_completion_metrics: dict[str, float | bool] = {"hermes_rpc_elapsed_ms": 0.0, "session_reused": False}

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
        started = time.perf_counter()
        self.last_completion_metrics = {"hermes_rpc_elapsed_ms": 0.0, "session_reused": bool(resume)}
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
                self.last_completion_metrics = {"hermes_rpc_elapsed_ms": round((time.perf_counter() - started) * 1000, 2), "session_reused": bool(resume)}
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
