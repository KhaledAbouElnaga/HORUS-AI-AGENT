"""Official non-SIP WhatsApp Calling WebRTC/media boundary.

The module keeps Meta signaling separate from the media engine. Credentials are
injected by the caller and never logged. ``aiortc`` is imported lazily so the
control-plane and pipeline tests remain deterministic without a live account.
"""
from __future__ import annotations

import json
import queue
import threading
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .whatsapp_calling import WhatsAppCallingAdapter


class MediaContractError(ValueError):
    pass


class CallControlError(RuntimeError):
    pass


class WebRtcEndpoint(Protocol):
    def answer(self, offer_sdp: str) -> str: ...
    def add_pcm_listener(self, listener: Callable[[bytes, int], None]) -> None: ...
    def queue_pcm(self, pcm: bytes, sample_rate: int = 48_000) -> None: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class CallAction:
    phone_number_id: str
    call_id: str
    action: str
    answer_sdp: str | None = None


class MetaCallingClient:
    """Minimal Graph call-control client; response bodies stay in-process."""

    def __init__(self, access_token: str, api_version: str = "v26.0", opener=urlopen):
        if not access_token:
            raise ValueError("access_token is required")
        self._access_token = access_token
        self.api_version = api_version
        self._opener = opener

    def send(self, action: CallAction) -> dict:
        if action.action not in {"pre_accept", "accept", "reject", "terminate"}:
            raise MediaContractError("unsupported call action")
        if action.action in {"pre_accept", "accept"} and not action.answer_sdp:
            raise MediaContractError("accept actions require answer SDP")
        payload = {"messaging_product": "whatsapp", "call_id": action.call_id, "action": action.action}
        if action.answer_sdp is not None:
            payload["session"] = {"sdp_type": "answer", "sdp": action.answer_sdp}
        request = Request(
            f"https://graph.facebook.com/{self.api_version}/{action.phone_number_id}/calls",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._access_token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener(request, timeout=30) as response:
                status, body = response.status, response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise CallControlError("Meta call-control request failed") from exc
        if status < 200 or status >= 300:
            raise CallControlError("Meta call-control request rejected")
        try:
            decoded = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise CallControlError("Meta call-control returned invalid JSON") from exc
        return decoded if isinstance(decoded, dict) else {}


class VoiceTurnProcessor(Protocol):
    def process_utterance(self, pcm_48khz: bytes, sample_rate: int) -> Iterable[bytes]: ...


class PipelineVoiceTurnProcessor:
    """Concrete PCM → STT → HORUS → TTS processor for one call session."""

    def __init__(self, session_id: str, transcriber, runtime, synthesize: Callable[[str], bytes | Iterable[bytes]], tts_sample_rate: int = 48_000):
        self.session_id = session_id
        self.transcriber = transcriber
        self.runtime = runtime
        self.synthesize = synthesize
        self.tts_sample_rate = tts_sample_rate

    @staticmethod
    def _resample(pcm: bytes, source_rate: int, target_rate: int) -> bytes:
        if source_rate == target_rate:
            return pcm
        try:
            from av import AudioFrame, AudioResampler
            frame = AudioFrame(format="s16", layout="mono", samples=len(pcm) // 2)
            frame.sample_rate = source_rate
            frame.planes[0].update(pcm)
            resampler = AudioResampler(format="s16", layout="mono", rate=target_rate)
            return b"".join(f.to_ndarray().tobytes() for f in resampler.resample(frame))
        except (ImportError, ValueError) as exc:
            raise MediaContractError("PCM resampling is unavailable") from exc

    @classmethod
    def _to_16khz(cls, pcm: bytes, sample_rate: int) -> bytes:
        return cls._resample(pcm, sample_rate, 16_000)

    def process_utterance(self, pcm_48khz: bytes, sample_rate: int) -> Iterable[bytes]:
        pcm_16khz = self._to_16khz(pcm_48khz, sample_rate)
        rows = self.transcriber.run(pcm_16khz)
        if not rows or not rows[-1].text.strip():
            return []
        response = "".join(self.runtime.stream_turn(self.session_id, rows[-1].text, None))
        outputs: list[bytes] = []
        for phrase in response.split(". "):
            phrase = phrase.strip()
            if not phrase:
                continue
            rendered = self.synthesize(phrase + ("." if not phrase.endswith(".") else ""))
            if isinstance(rendered, (bytes, bytearray)):
                outputs.append(self._resample(bytes(rendered), self.tts_sample_rate, 48_000))
            else:
                outputs.extend(self._resample(bytes(chunk), self.tts_sample_rate, 48_000) for chunk in rendered if chunk)
        return outputs


class DuplexVoiceBridge:
    """Routes decoded inbound PCM through STT/runtime/TTS and queues output."""

    def __init__(self, processor: VoiceTurnProcessor, max_output_chunks: int = 64):
        self.processor = processor
        self.output: queue.Queue[tuple[bytes, int]] = queue.Queue(maxsize=max_output_chunks)
        self.dropped_output = 0
        self._closed = False
        self._lock = threading.Lock()

    def on_pcm(self, pcm: bytes, sample_rate: int) -> None:
        if not pcm or self._closed:
            return
        for output_pcm in self.processor.process_utterance(pcm, sample_rate):
            if not output_pcm:
                continue
            try:
                self.output.put_nowait((bytes(output_pcm), 48_000))
            except queue.Full:
                self.dropped_output += 1

    def next_output(self, timeout: float = 0.1) -> tuple[bytes, int] | None:
        try:
            return self.output.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        with self._lock:
            self._closed = True
            while not self.output.empty():
                try:
                    self.output.get_nowait()
                except queue.Empty:
                    break


class LiveCallingCoordinator:
    """Accepts a verified normalized connect and attaches the duplex bridge."""

    def __init__(self, adapter: WhatsAppCallingAdapter, client: MetaCallingClient, endpoint_factory: Callable[[], WebRtcEndpoint], voice: DuplexVoiceBridge):
        self.adapter = adapter
        self.client = client
        self.endpoint_factory = endpoint_factory
        self.voice = voice
        self.endpoints: dict[str, WebRtcEndpoint] = {}
        self._workers: dict[str, threading.Thread] = {}

    def _pump_output(self, session_id: str, endpoint: WebRtcEndpoint) -> None:
        while self.endpoints.get(session_id) is endpoint:
            item = self.voice.next_output(timeout=0.2)
            if item is not None:
                try:
                    endpoint.queue_pcm(*item)
                except Exception:
                    return

    def accept_connect(self, envelope: dict) -> dict:
        if envelope.get("kind") != "incoming":
            raise MediaContractError("connect acceptance requires normalized incoming event")
        session = envelope.get("session") or {}
        offer = session.get("sdp")
        if not isinstance(offer, str) or not offer:
            raise MediaContractError("connect event is missing SDP offer")
        result = self.adapter.ingest(envelope)
        if result.get("status") != "accepted":
            return result
        endpoint = self.endpoint_factory()
        endpoint.add_pcm_listener(self.voice.on_pcm)
        answer = endpoint.answer(offer)
        phone_id = envelope["phone_number_id"]
        call_id = envelope["call_id"]
        endpoint_key = result["session_id"]
        self.client.send(CallAction(phone_id, call_id, "pre_accept", answer))
        self.client.send(CallAction(phone_id, call_id, "accept", answer))
        self.endpoints[endpoint_key] = endpoint
        worker = threading.Thread(target=self._pump_output, args=(endpoint_key, endpoint), daemon=True)
        self._workers[endpoint_key] = worker
        worker.start()
        return {"status": "accepted", "session_id": endpoint_key, "media": "negotiated"}

    def hangup(self, envelope: dict) -> dict:
        result = self.adapter.ingest(envelope)
        sid = result.get("session_id")
        endpoint = self.endpoints.pop(sid, None)
        self._workers.pop(sid, None)
        if endpoint is not None:
            endpoint.close()
        self.voice.close()
        return result


def aiortc_endpoint_factory() -> WebRtcEndpoint:
    """Create the real aiortc endpoint; dependency is intentionally lazy."""
    import asyncio
    try:
        from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
        from av import AudioFrame
    except ImportError as exc:
        raise RuntimeError("aiortc and av are required for live WebRTC media") from exc

    class OutputTrack(MediaStreamTrack):
        kind = "audio"

        def __init__(self):
            super().__init__()
            self.frames: queue.Queue[tuple[bytes, int]] = queue.Queue(maxsize=64)
            self.samples = 0

        async def recv(self):
            import asyncio
            pcm, rate = await asyncio.to_thread(self.frames.get)
            frame = AudioFrame(format="s16", layout="mono", samples=len(pcm) // 2)
            frame.sample_rate = rate
            frame.planes[0].update(pcm)
            frame.pts = self.samples
            frame.time_base = __import__("fractions").Fraction(1, rate)
            self.samples += frame.samples
            return frame

    class Endpoint:
        def __init__(self):
            self.loop = asyncio.new_event_loop()
            self.ready = threading.Event()
            self.listeners: list[Callable[[bytes, int], None]] = []
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            if not self.ready.wait(10):
                raise RuntimeError("aiortc event loop did not start")

        def _run(self):
            asyncio.set_event_loop(self.loop)
            self.pc = RTCPeerConnection()
            self.out = OutputTrack()
            self.pc.addTrack(self.out)
            self._bind_track()
            self.ready.set()
            self.loop.run_forever()

        def _bind_track(self):
            @self.pc.on("track")
            def on_track(track):
                if track.kind != "audio":
                    return
                async def consume():
                    while True:
                        frame = await track.recv()
                        pcm = frame.to_ndarray().tobytes()
                        for listener in self.listeners:
                            listener(pcm, frame.sample_rate or 48_000)
                import asyncio
                asyncio.create_task(consume())

        def answer(self, offer_sdp: str) -> str:
            async def negotiate():
                await self.pc.setRemoteDescription(RTCSessionDescription(sdp=offer_sdp, type="offer"))
                answer = await self.pc.createAnswer()
                await self.pc.setLocalDescription(answer)
                return self.pc.localDescription.sdp
            return asyncio.run_coroutine_threadsafe(negotiate(), self.loop).result(30)

        def add_pcm_listener(self, listener): self.listeners.append(listener)
        def queue_pcm(self, pcm, sample_rate=48_000): self.out.frames.put_nowait((pcm, sample_rate))
        def close(self):
            future = asyncio.run_coroutine_threadsafe(self.pc.close(), self.loop)
            future.result(10)
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=10)

    return Endpoint()
