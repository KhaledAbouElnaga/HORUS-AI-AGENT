import asyncio
import queue
import threading
import time

import pytest
from aiortc.mediastreams import MediaStreamError

from horus_local_voice.whatsapp_calling import WhatsAppCallingAdapter
from horus_local_voice.whatsapp_media import (
    CallAction, DuplexVoiceBridge, LiveCallingCoordinator, MediaContractError, MetaCallingClient,
    PipelineVoiceTurnProcessor, aiortc_endpoint_factory,
)


class Runtime:
    def __init__(self): self.calls = []
    def open_session(self, sid): self.calls.append(("open", sid))
    def ingest_media(self, sid, media): self.calls.append(("media", sid, media))
    def cancel(self, sid): self.calls.append(("cancel", sid))
    def close_session(self, sid): self.calls.append(("close", sid))


class Endpoint:
    def __init__(self): self.offer = None; self.listeners = []; self.queued = []; self.closed = False
    def answer(self, offer): self.offer = offer; return "answer-sdp"
    def add_pcm_listener(self, listener): self.listeners.append(listener)
    def queue_pcm(self, pcm, sample_rate=48000): self.queued.append((pcm, sample_rate))
    def close(self): self.closed = True


class Client:
    def __init__(self): self.actions = []
    def send(self, action): self.actions.append(action); return {}


class Processor:
    def __init__(self): self.inputs = []
    def process_utterance(self, pcm, rate):
        self.inputs.append((pcm, rate))
        return [b"tts-pcm"]


def env(kind="incoming", event_id="e1"):
    return {"event_id": event_id, "kind": kind, "call_id": "call-1", "user_id": "user-1", "phone_number_id": "phone-1", "session": {"sdp": "offer-sdp"}}


def test_live_coordinator_negotiates_and_uses_two_stage_accept():
    runtime = Runtime(); endpoint = Endpoint(); client = Client(); processor = Processor()
    coordinator = LiveCallingCoordinator(WhatsAppCallingAdapter(runtime), client, lambda: endpoint, DuplexVoiceBridge(processor))
    result = coordinator.accept_connect(env())
    assert result["status"] == "accepted" and result["media"] == "negotiated"
    assert endpoint.offer == "offer-sdp"
    assert [a.action for a in client.actions] == ["pre_accept", "accept"]
    assert all(a.answer_sdp == "answer-sdp" for a in client.actions)
    endpoint.listeners[0](b"input-pcm", 48000)
    assert processor.inputs == [(b"input-pcm", 48000)]
    coordinator.hangup({**env("hangup", "e2"), "session": None})
    assert endpoint.closed


def test_output_pump_backpressures_instead_of_dropping_worker_on_full_track_queue():
    class Voice:
        def __init__(self): self.sent = False
        def next_output(self, timeout=0.1):
            if not self.sent:
                self.sent = True
                return b"pcm", 48_000
            time.sleep(0.01)
            return None

    class BackpressuredEndpoint(Endpoint):
        def __init__(self): super().__init__(); self.attempts = 0
        def queue_pcm(self, pcm, sample_rate=48_000):
            self.attempts += 1
            if self.attempts < 3:
                raise queue.Full
            super().queue_pcm(pcm, sample_rate)

    voice = Voice(); endpoint = BackpressuredEndpoint()
    coordinator = LiveCallingCoordinator(WhatsAppCallingAdapter(Runtime()), Client(), lambda: endpoint, voice)
    coordinator.endpoints["session"] = endpoint
    worker = threading.Thread(target=coordinator._pump_output, args=("session", endpoint, voice))
    worker.start()
    deadline = time.monotonic() + 1
    while not endpoint.queued and time.monotonic() < deadline:
        time.sleep(0.01)
    coordinator.endpoints.pop("session", None)
    worker.join(timeout=1)
    assert endpoint.queued == [(b"pcm", 48_000)]
    assert endpoint.attempts == 3



def test_pending_duplicate_cannot_release_single_call_reservation():
    entered = threading.Event(); release = threading.Event(); results = []

    class Voice:
        def __init__(self, sid): self.session_id = sid
        def start(self): entered.set(); release.wait(1)
        def on_pcm(self, pcm, rate): pass
        def on_playout_pcm(self, pcm, rate): pass
        def next_output(self, timeout=0.1): return None
        def flush(self): pass
        def close(self): pass

    coordinator = LiveCallingCoordinator(
        WhatsAppCallingAdapter(Runtime()), Client(), Endpoint,
        voice_factory=Voice,
    )
    worker = threading.Thread(target=lambda: results.append(coordinator.accept_connect(env())))
    worker.start(); assert entered.wait(1)
    assert coordinator.accept_connect(env(event_id="duplicate")) == {"status": "duplicate"}
    other = env(event_id="other"); other["call_id"] = "call-2"
    assert coordinator.accept_connect(other) == {"status": "busy"}
    release.set(); worker.join(timeout=2)
    assert results and results[0]["status"] == "accepted"
    coordinator.hangup({**env("hangup", "done"), "session": None})


def test_hangup_during_acceptance_cancels_pending_call_without_ghost_session():
    entered = threading.Event(); release = threading.Event(); outcome = []; voices = []

    class Voice:
        def __init__(self, sid): self.session_id = sid; self.closed = False; voices.append(self)
        def start(self): entered.set(); release.wait(1)
        def on_pcm(self, pcm, rate): pass
        def on_playout_pcm(self, pcm, rate): pass
        def next_output(self, timeout=0.1): return None
        def flush(self): pass
        def close(self): self.closed = True

    coordinator = LiveCallingCoordinator(
        WhatsAppCallingAdapter(Runtime()), Client(), Endpoint,
        voice_factory=Voice,
    )

    def accept():
        try:
            coordinator.accept_connect(env())
        except Exception as exc:
            outcome.append(exc)

    worker = threading.Thread(target=accept)
    worker.start(); assert entered.wait(1)
    assert coordinator.hangup({**env("hangup", "cancel"), "session": None})["status"] == "accepted"
    release.set(); worker.join(timeout=2)
    assert outcome and isinstance(outcome[0], MediaContractError)
    assert not coordinator.endpoints and coordinator._active_call_id is None and coordinator._pending_call_id is None
    assert voices[0].closed



def test_live_coordinator_rejects_second_concurrent_call_to_preserve_isolation():
    runtime = Runtime(); client = Client(); processor = Processor()
    first = Endpoint()
    coordinator = LiveCallingCoordinator(WhatsAppCallingAdapter(runtime), client, lambda: first, DuplexVoiceBridge(processor))
    assert coordinator.accept_connect(env())["status"] == "accepted"
    second = env(event_id="e2")
    second["call_id"] = "call-2"
    assert coordinator.accept_connect(second) == {"status": "busy"}
    assert len(client.actions) == 2
    coordinator.hangup({**env("hangup", "e3"), "session": None})


def test_live_coordinator_voice_factory_closes_session_and_allows_fresh_call():
    runtime = Runtime(); client = Client(); endpoints = []; voices = []

    class Voice:
        def __init__(self, sid): self.session_id = sid; self.started = False; self.closed = False
        def start(self): self.started = True
        def on_pcm(self, pcm, rate): pass
        def on_playout_pcm(self, pcm, rate): pass
        def next_output(self, timeout=0.1): return None
        def flush(self): pass
        def close(self): self.closed = True

    def endpoint_factory():
        endpoint = Endpoint(); endpoints.append(endpoint); return endpoint

    def voice_factory(sid):
        voice = Voice(sid); voices.append(voice); return voice

    coordinator = LiveCallingCoordinator(
        WhatsAppCallingAdapter(runtime), client, endpoint_factory,
        voice_factory=voice_factory,
    )
    assert coordinator.accept_connect(env())["status"] == "accepted"
    assert voices[0].started and voices[0].session_id == "wa:phone-1:user-1:call-1"
    coordinator.hangup({**env("hangup", "e2"), "session": None})
    assert voices[0].closed and endpoints[0].closed

    fresh = env(event_id="e3")
    fresh["call_id"] = "call-2"
    assert coordinator.accept_connect(fresh)["status"] == "accepted"
    assert len(voices) == 2 and voices[1] is not voices[0] and voices[1].started
    coordinator.hangup({**fresh, "kind": "hangup", "event_id": "e4", "session": None})
    assert voices[1].closed


def test_adapter_ingest_failure_does_not_poison_busy_gate(monkeypatch):
    runtime = Runtime(); endpoint = Endpoint(); client = Client()
    coordinator = LiveCallingCoordinator(
        WhatsAppCallingAdapter(runtime), client, lambda: endpoint, DuplexVoiceBridge(Processor())
    )
    original = coordinator.adapter.ingest
    monkeypatch.setattr(coordinator.adapter, "ingest", lambda event: (_ for _ in ()).throw(RuntimeError("invalid ingress")))
    with pytest.raises(RuntimeError, match="invalid ingress"):
        coordinator.accept_connect(env())
    monkeypatch.setattr(coordinator.adapter, "ingest", original)
    second = env(event_id="e2")
    second["call_id"] = "call-2"
    assert coordinator.accept_connect(second)["status"] == "accepted"



def test_accept_failure_rolls_back_and_meta_retry_is_accepted():
    runtime = Runtime(); endpoint = Endpoint()
    class RetryingClient:
        def __init__(self): self.actions = []; self.fail_once = True
        def send(self, action):
            self.actions.append(action)
            if action.action == "accept" and self.fail_once:
                self.fail_once = False
                from horus_local_voice.whatsapp_media import CallControlError
                raise CallControlError("rejected", http_status=500)
            return {}
    stages = []
    client = RetryingClient()
    coordinator = LiveCallingCoordinator(WhatsAppCallingAdapter(runtime), client, lambda: endpoint, DuplexVoiceBridge(Processor()), stage_logger=lambda s, m: stages.append((s, m)))
    try:
        coordinator.accept_connect(env())
    except Exception:
        pass
    else:
        raise AssertionError("first accept should fail")
    assert coordinator.adapter.sessions["wa:phone-1:user-1:call-1"].state == "NEW"
    assert coordinator.accept_connect(env())["status"] == "accepted"
    assert [a.action for a in client.actions] == ["pre_accept", "accept", "pre_accept", "accept"]
    assert any(stage == "control_accept" and metrics["status"] == "error" and metrics["http_status"] == 500 for stage, metrics in stages)


def test_duplicate_connect_does_not_negotiate_again():
    runtime = Runtime(); endpoint = Endpoint(); client = Client()
    c = LiveCallingCoordinator(WhatsAppCallingAdapter(runtime), client, lambda: endpoint, DuplexVoiceBridge(Processor()))
    assert c.accept_connect(env())["status"] == "accepted"
    assert c.accept_connect(env())["status"] == "duplicate"
    assert len(client.actions) == 2


def test_meta_client_builds_non_sip_action_without_logging_or_leaking_token():
    requests = []
    class Response:
        status = 200
        def read(self): return b'{"success":true}'
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def opener(request, timeout): requests.append(request); return Response()
    client = MetaCallingClient("SECRET-NOT-LOGGED", opener=opener)
    assert client.send(CallAction("phone", "call", "terminate")) == {"success": True}
    body = requests[0].data.decode()
    assert '"action": "terminate"' in body
    assert "SECRET-NOT-LOGGED" not in body
    assert requests[0].get_header("Authorization") == "Bearer SECRET-NOT-LOGGED"


def test_realtime_backend_build_does_not_load_legacy_voice_stack(monkeypatch):
    import builtins
    import scripts.run_whatsapp_webhook_server as runner
    from horus_local_voice.realtime_voice import RealtimeVoiceBridge

    values = {
        "HORUS_VOICE_BACKEND": "realtime",
        "WHATSAPP_WEBHOOK_VERIFY_TOKEN": "not-a-real-secret",
        "META_APP_SECRET": "not-a-real-secret",
        "WHATSAPP_ACCESS_TOKEN": "not-a-real-token",
        "HORUS_ROOT": "D:/HORUS/horus-core",
        "OPENAI_API_KEY": "not-a-real-key",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PIPER_AR_VOICE", raising=False)
    monkeypatch.delenv("PIPER_EN_VOICE", raising=False)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {"faster_whisper", "webrtcvad", "piper"}:
            raise AssertionError(f"legacy dependency loaded in realtime mode: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    coordinator = runner.build_live_coordinator()
    assert coordinator.voice is None
    bridge = coordinator.voice_factory("isolated-realtime-session")
    assert isinstance(bridge, RealtimeVoiceBridge)
    assert bridge.model == "gpt-realtime-2.1"
    assert bridge.tool_runtime.free_provider is None
    bridge.close()


def test_voice_backend_defaults_legacy_and_rejects_unknown(monkeypatch):
    import scripts.run_whatsapp_webhook_server as runner

    monkeypatch.delenv("HORUS_VOICE_BACKEND", raising=False)
    assert runner.voice_backend() == "legacy"
    monkeypatch.setenv("HORUS_VOICE_BACKEND", "unsupported")
    with pytest.raises(RuntimeError, match="HORUS_VOICE_BACKEND"):
        runner.voice_backend()


def test_runnable_entrypoint_installs_live_media_handler(monkeypatch):
    import scripts.run_whatsapp_webhook_server as runner

    class Coordinator:
        def __init__(self): self.events = []
        def accept_connect(self, event): self.events.append(("connect", event)); return {"status": "accepted"}
        def hangup(self, event): self.events.append(("terminate", event)); return {"status": "accepted"}

    coordinator = Coordinator()
    monkeypatch.setattr(runner, "build_live_coordinator", lambda: coordinator)
    runner.webhook.event_handler = None
    assert runner.configure_live_media() is coordinator
    result = runner.webhook.event_handler({"kind": "incoming"})
    assert result == {"status": "accepted"}
    assert coordinator.events == [("connect", {"kind": "incoming"})]


    class Transcriber:
        def run(self, pcm):
            assert pcm == b"audio"
            return [type("R", (), {"text": "hello"})()]

    class Runtime:
        def stream_turn(self, sid, text, cancel):
            assert (sid, text) == ("session", "hello")
            return ["reply"]

    processor = PipelineVoiceTurnProcessor("session", Transcriber(), Runtime(), lambda text: text.encode())
    assert list(processor.process_utterance(b"audio", 16_000)) == [b"reply."]


def test_pipeline_chunks_arabic_question_boundaries_for_tts():
    class Transcriber:
        def run(self, pcm): return [type("R", (), {"text": "سؤال"})()]
    class Runtime:
        last_turn_metrics = {"hermes_rpc_elapsed_ms": 12.0, "session_reused": True}
        def stream_turn(self, sid, text, cancel): return ["أولاً؟ ثانياً."]
    spoken = []
    processor = PipelineVoiceTurnProcessor("session", Transcriber(), Runtime(), lambda text: spoken.append(text) or b"\x01\x00")
    assert list(processor.process_utterance(b"audio", 16_000)) == [b"\x01\x00", b"\x01\x00"]
    assert spoken == ["أولاً؟", "ثانياً."]


def test_vad_accumulates_until_silence_boundary():
    from horus_local_voice.whatsapp_media import VadEndpointAccumulator
    vad = VadEndpointAccumulator(end_silence_ms=60, min_utterance_ms=120)
    sequence = iter([True] * 3 + [False] * 4)
    vad.vad.is_speech = lambda frame, rate: next(sequence)
    frame = bytes([1, 0]) * 960
    completed = []
    for _ in range(7):
        completed.extend(vad.push(frame, 48_000))
    assert len(completed) == 1
    assert len(completed[0]) == 6 * len(frame)


def test_vad_flushes_open_utterance_without_waiting_for_more_rtp():
    from horus_local_voice.whatsapp_media import VadEndpointAccumulator
    vad = VadEndpointAccumulator(start_voiced_frames=1, min_utterance_ms=20)
    vad.vad.is_speech = lambda frame, rate: True
    frame = bytes([1, 0]) * 960
    vad.push(frame, 48_000)
    assert vad.flush() == [frame]


def test_vad_rejects_short_noise_and_keeps_phone_question_with_pause_as_one_turn():
    from horus_local_voice.whatsapp_media import VadEndpointAccumulator
    vad = VadEndpointAccumulator(start_voiced_frames=3, end_silence_ms=700, min_utterance_ms=800)
    frame = bytes([1, 0]) * 960
    sequence = iter([True, False, True] + [True] * 12 + [False] * 10 + [True] * 16 + [False] * 35)
    vad.vad.is_speech = lambda _frame, _rate: next(sequence)
    completed = []
    for _ in range(76):
        completed.extend(vad.push(frame, 48_000))
    assert len(completed) == 1
    assert len(completed[0]) == 74 * len(frame)


def test_media_stream_error_is_normal_track_closure():
    from horus_local_voice.whatsapp_media import consume_remote_audio_track
    class Track:
        async def recv(self): raise MediaStreamError()
    asyncio.run(consume_remote_audio_track(Track(), []))


def test_hangup_during_processing_discards_stale_output():
    import threading
    started = threading.Event(); release = threading.Event()
    class Slow:
        def process_utterance(self, pcm, rate):
            started.set(); release.wait(2); return [b"stale"]
    bridge = DuplexVoiceBridge(Slow(), background_processing=True)
    bridge.on_pcm(b"input", 48_000)
    assert started.wait(1)
    bridge.close(); release.set()
    assert bridge.next_output(timeout=0.3) is None


def test_half_duplex_suppresses_inbound_echo_during_playback_and_tail():
    events = []
    processor = Processor()
    bridge = DuplexVoiceBridge(processor, stage_logger=lambda stage, metrics: events.append((stage, metrics)), playback_tail_ms=800)
    bridge.on_pcm(b"user", 48_000)
    assert bridge.next_output() == (b"tts-pcm", 48_000)
    bridge.on_playout_pcm(b"\x01\x00" * 960, 48_000)
    bridge.on_pcm(b"echo", 48_000)
    assert processor.inputs == [(b"user", 48_000)]
    assert any(stage == "inbound_suppressed_playback" for stage, _ in events)
    assert any(stage == "turn_to_first_audio" for stage, _ in events)
    bridge.close()


def test_newer_turn_replaces_queued_fragment_and_drops_stale_active_reply():
    import threading
    import time
    started = threading.Event(); release = threading.Event()
    events = []
    class Slow:
        def __init__(self): self.calls = []
        def process_utterance(self, pcm, rate):
            self.calls.append(pcm)
            started.set(); release.wait(1)
            return [pcm + b"-reply"]
    processor = Slow()
    bridge = DuplexVoiceBridge(processor, background_processing=True, stage_logger=lambda stage, metrics: events.append((stage, metrics)))
    bridge.on_pcm(b"first", 48_000)
    assert started.wait(1)
    bridge.on_pcm(b"fragment", 48_000)
    bridge.on_pcm(b"latest", 48_000)
    release.set()
    deadline = time.time() + 1
    output = None
    while time.time() < deadline and output is None:
        output = bridge.next_output(timeout=0.05)
    assert output == (b"latest-reply", 48_000)
    assert bridge.turn_replacements == 1 and bridge.stale_turn_drops >= 1
    assert any(stage == "turn_replaced" for stage, _ in events)
    assert any(stage == "stale_turn_dropped" for stage, _ in events)
    bridge.close()


def test_duplex_bridge_worker_survives_provider_failure_and_processes_next_turn():
    import time

    events = []

    class Flaky:
        def __init__(self):
            self.calls = 0

        def process_utterance(self, pcm, rate):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("all Hermes OpenCode Free models failed")
            return [b"recovered"]

    bridge = DuplexVoiceBridge(Flaky(), background_processing=True, stage_logger=lambda s, m: events.append((s, m)))
    bridge.on_pcm(b"first", 48_000)
    time.sleep(0.05)
    bridge.on_pcm(b"second", 48_000)
    deadline = time.time() + 1
    item = None
    while time.time() < deadline and item is None:
        item = bridge.next_output(timeout=0.05)
    assert item == (b"recovered", 48_000)
    assert any(stage == "turn_error" for stage, _ in events)
    assert bridge._worker is not None and bridge._worker.is_alive()
    bridge.close()


def test_duplex_bridge_is_bounded_and_closes_output():
    processor = Processor(); bridge = DuplexVoiceBridge(processor, max_output_chunks=1)
    bridge.on_pcm(b"a", 48000)
    assert bridge.next_output() == (b"tts-pcm", 48000)
    bridge._playback_until = 0; bridge.on_pcm(b"b", 48000)
    bridge._playback_until = 0; bridge.on_pcm(b"c", 48000)
    assert bridge.dropped_output == 1
    bridge.close()
    assert bridge.next_output(timeout=0) is None


def test_duplex_bridge_worker_stays_alive_after_provider_failure():
    import time

    events = []

    class Broken:
        def process_utterance(self, pcm, rate):
            raise RuntimeError("provider failure")

    bridge = DuplexVoiceBridge(Broken(), background_processing=True, stage_logger=lambda s, m: events.append((s, m)))
    bridge.on_pcm(b"input", 48_000)
    time.sleep(0.05)
    assert bridge._worker is not None and bridge._worker.is_alive()
    assert any(stage == "turn_error" for stage, _ in events)
    bridge.close()


def test_aiortc_endpoint_close_is_idempotent():
    endpoint = aiortc_endpoint_factory()
    endpoint.close()
    endpoint.close()
    assert not endpoint.thread.is_alive()


def test_output_track_delivers_pcm_immediately_after_silence_timeouts():
    endpoint = aiortc_endpoint_factory()
    loop = asyncio.new_event_loop()
    marker = (b"\x34\x12" * 960)
    played = []
    endpoint.add_output_listener(lambda pcm, rate: played.append((pcm, rate)))
    try:
        async def receive_after_silence():
            for _ in range(4):
                silence = await endpoint.out.recv()
                assert bytes(silence.planes[0]) == b"\x00" * 1920
            endpoint.queue_pcm(marker, 48_000)
            return await endpoint.out.recv()

        frame = loop.run_until_complete(receive_after_silence())
        assert bytes(frame.planes[0]) == marker
        assert played == [(marker, 48_000)]
    finally:
        # Release abandoned executor Queue.get calls in the buggy implementation
        # so the RED test exits cleanly instead of leaking its repro threads.
        for _ in range(8):
            try:
                endpoint.out.frames.put_nowait((b"\x00" * 1920, 48_000))
            except Exception:
                break
        endpoint.close()
        loop.close()


def test_output_track_preserves_multiframe_pcm_format_and_timestamps():
    endpoint = aiortc_endpoint_factory()
    loop = asyncio.new_event_loop()
    first = b"\x11\x00" * 960
    second = b"\x22\x00" * 960
    try:
        endpoint.queue_pcm(first + second, 48_000)

        async def receive_two():
            return await endpoint.out.recv(), await endpoint.out.recv()

        frame1, frame2 = loop.run_until_complete(receive_two())
        assert bytes(frame1.planes[0]) == first
        assert bytes(frame2.planes[0]) == second
        assert frame1.format.name == frame2.format.name == "s16"
        assert frame1.layout.name == frame2.layout.name == "mono"
        assert frame1.samples == frame2.samples == 960
        assert frame1.sample_rate == frame2.sample_rate == 48_000
        assert (frame1.pts, frame2.pts) == (0, 960)
        assert str(frame1.time_base) == str(frame2.time_base) == "1/48000"
    finally:
        endpoint.close()
        loop.close()


def test_output_track_paces_frames_at_twenty_milliseconds():
    endpoint = aiortc_endpoint_factory()
    loop = asyncio.new_event_loop()
    try:
        async def receive_four():
            started = loop.time()
            for _ in range(4):
                await endpoint.out.recv()
            return loop.time() - started

        elapsed = loop.run_until_complete(receive_four())
        assert 0.045 <= elapsed < 0.25
    finally:
        endpoint.close()
        loop.close()


def test_output_track_logs_queue_placement_separately_from_track_consumption():
    events = []
    endpoint = aiortc_endpoint_factory(stage_logger=lambda stage, metrics: events.append((stage, metrics)))
    loop = asyncio.new_event_loop()
    try:
        endpoint.queue_pcm(b"\x01\x00" * 960, 48_000)
        assert [stage for stage, _ in events] == ["outbound_pcm_placed"]
        loop.run_until_complete(endpoint.out.recv())
        assert [stage for stage, _ in events] == ["outbound_pcm_placed", "outbound_pcm_consumed"]
    finally:
        endpoint.close()
        loop.close()


def test_output_track_telemetry_failure_cannot_interrupt_pcm_delivery():
    def broken_logger(stage, metrics):
        raise RuntimeError("telemetry unavailable")

    endpoint = aiortc_endpoint_factory(stage_logger=broken_logger)
    loop = asyncio.new_event_loop()
    marker = b"\x21\x43" * 960
    try:
        endpoint.queue_pcm(marker, 48_000)
        frame = loop.run_until_complete(endpoint.out.recv())
        assert bytes(frame.planes[0]) == marker
    finally:
        endpoint.close()
        loop.close()


def test_endpoint_rejects_pcm_after_close_without_scheduling_stats():
    endpoint = aiortc_endpoint_factory()
    endpoint.close()
    try:
        endpoint.queue_pcm(b"\x00\x00" * 960, 48_000)
    except MediaContractError as exc:
        assert "closed" in str(exc)
    else:
        raise AssertionError("closed endpoint accepted PCM")


def test_queue_pcm_overlap_with_close_does_not_raise_closed_loop_error():
    import threading

    logger_entered = threading.Event()
    release_logger = threading.Event()
    errors = []

    def blocking_logger(stage, metrics):
        if stage == "outbound_pcm_placed":
            logger_entered.set()
            release_logger.wait(2)

    endpoint = aiortc_endpoint_factory(stage_logger=blocking_logger)

    def enqueue():
        try:
            endpoint.queue_pcm(b"\x22\x11" * 960, 48_000)
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=enqueue)
    worker.start()
    assert logger_entered.wait(1)
    endpoint.close()
    release_logger.set()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert errors == []


def test_aiortc_loopback_transmits_nonzero_pcm_and_exposes_sender_stats():
    from array import array
    import math
    import struct

    from aiortc import RTCPeerConnection, RTCSessionDescription

    async def scenario():
        events = []
        endpoint = aiortc_endpoint_factory(stage_logger=lambda stage, metrics: events.append((stage, metrics)))
        remote = RTCPeerConnection()
        tracks = []

        @remote.on("track")
        def on_track(track):
            tracks.append(track)

        try:
            remote.addTransceiver("audio", direction="recvonly")
            offer = await remote.createOffer()
            await remote.setLocalDescription(offer)
            answer_sdp = await asyncio.to_thread(endpoint.answer, remote.localDescription.sdp)
            await remote.setRemoteDescription(RTCSessionDescription(sdp=answer_sdp, type="answer"))
            for _ in range(100):
                if tracks and remote.connectionState == "connected":
                    break
                await asyncio.sleep(0.02)
            assert tracks and remote.connectionState == "connected"

            baseline_frames = [await asyncio.wait_for(tracks[0].recv(), timeout=1) for _ in range(4)]
            assert all(not any(frame.to_ndarray().tobytes()) for frame in baseline_frames)
            baseline = endpoint.sender_stats()

            samples = [int(12_000 * math.sin(2 * math.pi * 440 * index / 48_000)) for index in range(960 * 5)]
            marker = b"".join(struct.pack("<h", sample) for sample in samples)
            endpoint.queue_pcm(marker, 48_000)
            decoded_level = 0
            for _ in range(20):
                frame = await asyncio.wait_for(tracks[0].recv(), timeout=1)
                decoded = array("h")
                decoded.frombytes(frame.to_ndarray().tobytes())
                decoded_level = max((abs(sample) for sample in decoded), default=0)
                if decoded_level > 500:
                    break
            assert decoded_level > 500

            media = endpoint.media_state()
            assert media["direction"] in {"sendonly", "sendrecv"}
            assert media["codec"] == "opus"
            stats = endpoint.sender_stats()
            assert stats["packets_sent"] > baseline["packets_sent"]
            assert stats["bytes_sent"] > baseline["bytes_sent"]
            assert any(stage == "outbound_pcm_consumed" for stage, _ in events)
            return events
        finally:
            await remote.close()
            endpoint.close()

    events = asyncio.run(scenario())
    assert any(stage == "outbound_media_negotiated" for stage, _ in events)
    assert any(stage == "outbound_rtp_stats" for stage, _ in events)


def test_tts_routes_arabic_and_english_with_nonempty_pcm():
    import scripts.run_whatsapp_webhook_server as runner

    class Voice:
        def __init__(self, pcm): self.pcm = pcm; self.calls = []
        def synthesize(self, text):
            self.calls.append(text)
            return [type("Chunk", (), {"audio_int16_bytes": self.pcm})()]

    arabic = Voice(b"\x01\x00")
    english = Voice(b"\x02\x00")
    events = []
    from horus_local_voice.streaming import script_route
    synthesize = runner.build_tts_synthesizer({"ar": arabic, "en": english}, script_route, lambda stage, metrics: events.append((stage, metrics)))
    assert synthesize("أهلا") == b"\x01\x00"
    assert synthesize("hello") == b"\x02\x00"
    assert arabic.calls == ["أهلا"] and english.calls == ["hello"]
    assert events == [("tts_route", {"tts_route": "ar", "pcm_bytes": 2}), ("tts_route", {"tts_route": "en", "pcm_bytes": 2})]


def test_bilingual_stt_compares_candidates_for_low_confidence_arabic_as_english():
    import numpy as np
    import scripts.run_whatsapp_webhook_server as runner

    class Model:
        def __init__(self): self.calls = []
        def transcribe(self, samples, **kwargs):
            self.calls.append(kwargs)
            language = kwargs.get("language")
            if language == "ar":
                text, quality = "مرحبا كيف حالك", -0.2
            elif language == "en":
                text, quality = "marhaban kayfa haluk", -2.8
            else:
                text, quality = "marhaban kayfa haluk", -2.8
            segment = type("Segment", (), {"text": text, "avg_logprob": quality, "no_speech_prob": 0.02})()
            return iter([segment]), type("Info", (), {"language": "en", "language_probability": 0.25})()

    model = Model()
    assert runner.build_bilingual_transcriber(model, np, 5)(b"\x00\x00" * 160) == "مرحبا كيف حالك"
    assert [call.get("language") for call in model.calls] == [None, "ar", "en"]
    assert all(call["vad_filter"] is False and call["condition_on_previous_text"] is False and call["beam_size"] == 5 for call in model.calls)


def test_bilingual_stt_preserves_confident_english_without_forced_arabic():
    import numpy as np
    import scripts.run_whatsapp_webhook_server as runner

    class Model:
        def __init__(self): self.calls = []
        def transcribe(self, samples, **kwargs):
            self.calls.append(kwargs)
            segment = type("Segment", (), {"text": "what is my schedule", "avg_logprob": -0.1, "no_speech_prob": 0.01})()
            return iter([segment]), type("Info", (), {"language": "en", "language_probability": 0.91})()

    model = Model()
    assert runner.build_bilingual_transcriber(model, np, 5)(b"\x00\x00" * 160) == "what is my schedule"
    assert [call.get("language") for call in model.calls] == [None]
