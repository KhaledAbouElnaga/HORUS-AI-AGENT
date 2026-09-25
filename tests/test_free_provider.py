import asyncio
import sys

import pytest

from horus_local_voice.free_provider import FREE_MODELS, HermesFreeProvider, _load_runner


def test_free_provider_uses_hermes_oneshot_primary_and_preserves_session():
    calls = []

    def runner(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return "free response", {"session_id": "hermes-session-1"}

    provider = HermesFreeProvider(runner)
    provider.bind_session("voice-session")
    result = asyncio.run(provider.complete([{"role": "user", "content": "hello"}]))

    assert result == ("free response", FREE_MODELS[0], 0.0)
    assert calls[0][1]["provider"] == "opencode-free"
    assert calls[0][1]["model"] == FREE_MODELS[0]
    assert calls[0][1]["use_config_toolsets"] is False
    assert calls[0][1]["resume"] is None

    asyncio.run(provider.complete([{"role": "user", "content": "again"}]))
    assert calls[1][1]["resume"] == "hermes-session-1"


def test_free_provider_falls_back_to_verified_second_model_without_credentials():
    calls = []

    def runner(prompt, **kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == FREE_MODELS[0]:
            raise RuntimeError("provider unavailable")
        return "fallback response", {"session_id": "fallback-session"}

    result = asyncio.run(HermesFreeProvider(runner).complete([{"role": "user", "content": "hello"}]))

    assert result == ("fallback response", FREE_MODELS[1], 0.0)
    assert calls == list(FREE_MODELS)


def test_free_provider_reports_failure_after_both_models():
    def runner(prompt, **kwargs):
        raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="all Hermes OpenCode Free models failed"):
        asyncio.run(HermesFreeProvider(runner).complete([]))


def test_rpc_subprocess_uses_utf8_for_arabic_output_and_stderr(monkeypatch, tmp_path):
    root = tmp_path / "fake-hermes"
    package = root / "hermes_cli"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "oneshot.py").write_text(
        "def _run_agent(*args, **kwargs):\n"
        "    print('تشخيص عربي 😀')\n"
        "    return 'أهلًا يا خالد — hello 😀', {'session_id': 'جلسة-١'}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_AGENT_ROOT", str(root))
    monkeypatch.setenv("HERMES_AGENT_PYTHON", sys.executable)

    response, result = _load_runner()(
        "مرحبا 😀", model="test", provider="test", use_config_toolsets=False, resume=None,
    )

    assert response == "أهلًا يا خالد — hello 😀"
    assert result == {"session_id": "جلسة-١"}
