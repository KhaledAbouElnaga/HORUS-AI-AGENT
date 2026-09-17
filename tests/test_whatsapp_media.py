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


def test_pcm_pipeline_reaches_stt_horus_and_tts():
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


def test_duplex_bridge_is_bounded_and_closes_output():
    processor = Processor(); bridge = DuplexVoiceBridge(processor, max_output_chunks=1)
    bridge.on_pcm(b"a", 48000)
    assert bridge.next_output() == (b"tts-pcm", 48000)
    bridge.on_pcm(b"b", 48000); bridge.on_pcm(b"c", 48000)
    assert bridge.dropped_output == 1
    bridge.close()
    assert bridge.next_output(timeout=0) is None
