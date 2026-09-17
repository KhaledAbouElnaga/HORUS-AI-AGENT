import asyncio

import pytest

from horus_local_voice.free_provider import FREE_MODELS, HermesFreeProvider


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
