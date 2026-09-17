import asyncio

from aiortc.mediastreams import MediaStreamError

from horus_local_voice.whatsapp_calling import WhatsAppCallingAdapter
from horus_local_voice.whatsapp_media import (
    CallAction, DuplexVoiceBridge, LiveCallingCoordinator, MetaCallingClient,
    PipelineVoiceTurnProcessor,
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




def test_vad_accumulates_until_silence_boundary():
    from horus_local_voice.whatsapp_media import VadEndpointAccumulator
    vad = VadEndpointAccumulator(end_silence_ms=60)
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
    vad = VadEndpointAccumulator()
    vad.vad.is_speech = lambda frame, rate: True
    frame = bytes([1, 0]) * 960
    vad.push(frame, 48_000)
    assert vad.flush() == [frame]


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


def test_duplex_bridge_is_bounded_and_closes_output():
    processor = Processor(); bridge = DuplexVoiceBridge(processor, max_output_chunks=1)
    bridge.on_pcm(b"a", 48000)
    assert bridge.next_output() == (b"tts-pcm", 48000)
    bridge.on_pcm(b"b", 48000); bridge.on_pcm(b"c", 48000)
    assert bridge.dropped_output == 1
    bridge.close()
    assert bridge.next_output(timeout=0) is None
