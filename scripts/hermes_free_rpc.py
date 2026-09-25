"""Process-boundary RPC for the Hermes OpenCode Free runner.

This file is executed by Hermes' interpreter, never imported by the voice venv.
It emits one UTF-8 JSON response on stdout; runner diagnostics are redirected
to UTF-8 stderr.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path


def _configure_utf8_streams() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="strict")
        except (AttributeError, OSError):
            pass


def main() -> int:
    _configure_utf8_streams()
    configured = os.environ.get("HERMES_AGENT_ROOT", "").strip()
    root = Path(configured).expanduser() if configured else Path.home() / "AppData" / "Local" / "hermes" / "hermes-agent"
    sys.path.insert(0, str(root))
    try:
        from hermes_cli.oneshot import _run_agent
    except Exception:
        print(json.dumps({"ok": False, "error": "runner_unavailable"}), flush=True)
        return 0
    try:
        request = json.loads(sys.stdin.readline())
        with contextlib.redirect_stdout(sys.stderr):
            response, result = _run_agent(
                request["prompt"], model=request["model"], provider=request["provider"],
                use_config_toolsets=False, resume=request.get("resume"),
            )
        print(json.dumps({"ok": True, "response": response, "session_id": result.get("session_id")}, ensure_ascii=False), flush=True)
    except Exception as exc:  # controlled boundary; details stay out of stdout/logs
        print(json.dumps({"ok": False, "error": type(exc).__name__}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
