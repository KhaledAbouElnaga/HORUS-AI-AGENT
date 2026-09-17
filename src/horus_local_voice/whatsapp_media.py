"""Official non-SIP WhatsApp Calling WebRTC/media boundary.

The module keeps Meta signaling separate from the media engine. Credentials are
injected by the caller and never logged. ``aiortc`` is imported lazily so the
control-plane and pipeline tests remain deterministic without a live account.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .whatsapp_calling import WhatsAppCallingAdapter


class MediaContractError(ValueError):
    pass


class CallControlError(RuntimeError):
    def __init__(self, message: str, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status


class WebRtcEndpoint(Protocol):
    def answer(self, offer_sdp: str) -> str: ...
    def add_pcm_listener(self, listener: Callable[[bytes, int], None]) -> None: ...
    def queue_pcm(self, pcm: bytes, sample_rate: int = 48_000) -> None: ...
    def media_state(self) -> dict: ...
    def sender_stats(self) -> dict: ...
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
        except HTTPError as exc:
            raise CallControlError("Meta call-control request failed", http_status=exc.code) from exc
        except (URLError, TimeoutError) as exc:
            raise CallControlError("Meta call-control request failed") from exc
        if status < 200 or status >= 300:
            raise CallControlError("Meta call-control request rejected", http_status=status)
        try:
            decoded = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise CallControlError("Meta call-control returned invalid JSON") from exc
        return decoded if isinstance(decoded, dict) else {}


class VoiceTurnProcessor(Protocol):
    def process_utterance(self, pcm_48khz: bytes, sample_rate: int) -> Iterable[bytes]: ...


class PipelineVoiceTurnProcessor:
    """Concrete PCM → STT → HORUS → TTS processor for one call session."""

    def __init__(self, session_id: str, transcriber, runtime, synthesize: Callable[[str], bytes | Iterable[bytes]], tts_sample_rate: int = 48_000, stage_logger: Callable[[str, dict], None] | None = None):
        self.session_id = session_id
        self.transcriber = transcriber
        self.runtime = runtime
        self.synthesize = synthesize
        self.tts_sample_rate = tts_sample_rate
        self.stage_logger = stage_logger or (lambda stage, metrics: None)

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
        started = time.perf_counter()
        pcm_16khz = self._to_16khz(pcm_48khz, sample_rate)
        rows = self.transcriber.run(pcm_16khz)
        self.stage_logger("stt_complete", {"elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})
        if not rows or not rows[-1].text.strip():
            return []
        response = "".join(self.runtime.stream_turn(self.session_id, rows[-1].text, None))
        self.stage_logger("horus_turn_complete", {"elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})
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
        self.stage_logger("tts_complete", {"elapsed_ms": round((time.perf_counter() - started) * 1000, 2), "chunks": len(outputs)})
        return outputs


class VadEndpointAccumulator:
    """Accumulate 20 ms PCM frames until speech begins and then ends."""

    def __init__(self, aggressiveness: int = 2, end_silence_ms: int = 240, max_utterance_ms: int = 15_000):
        try:
            import webrtcvad
        except ImportError as exc:
            raise MediaContractError("webrtcvad is required for live endpointing") from exc
        self.vad = webrtcvad.Vad(aggressiveness)
        self.end_frames = max(1, end_silence_ms // 20)
        self.max_frames = max(1, max_utterance_ms // 20)
        self._buffer = bytearray()
        self._utterance = bytearray()
        self._started = False
        self._silence = 0
        self._frames = 0

    def push(self, pcm: bytes, sample_rate: int) -> list[bytes]:
        if sample_rate not in {8_000, 16_000, 32_000, 48_000}:
            raise MediaContractError("unsupported VAD sample rate")
        frame_bytes = sample_rate * 2 // 50
        self._buffer.extend(pcm)
        completed: list[bytes] = []
        while len(self._buffer) >= frame_bytes:
            frame = bytes(self._buffer[:frame_bytes])
            del self._buffer[:frame_bytes]
            voiced = self.vad.is_speech(frame, sample_rate)
            if not self._started:
                if voiced:
                    self._started = True
                    self._silence = 0
                    self._frames = 0
                    self._utterance.clear()
                else:
                    continue
            self._utterance.extend(frame)
            self._frames += 1
            self._silence = 0 if voiced else self._silence + 1
            if self._silence >= self.end_frames or self._frames >= self.max_frames:
                completed.append(bytes(self._utterance))
                self._utterance.clear()
                self._started = False
                self._silence = 0
                self._frames = 0
        return completed

    def flush(self) -> list[bytes]:
        if not self._started or not self._utterance:
            return []
        result = [bytes(self._utterance)]
        self._utterance.clear()
        self._started = False
        self._silence = 0
        self._frames = 0
        return result


class DuplexVoiceBridge:
    """Routes decoded inbound PCM through STT/runtime/TTS and queues output."""

    def __init__(self, processor: VoiceTurnProcessor, max_output_chunks: int = 64, min_utterance_ms: int = 0, background_processing: bool = False, stage_logger: Callable[[str, dict], None] | None = None, endpointing: bool = False, end_silence_ms: int = 240):
        self.processor = processor
        self.output: queue.Queue[tuple[bytes, int]] = queue.Queue(maxsize=max_output_chunks)
        self.input_queue: queue.Queue[tuple[bytes, int] | None] = queue.Queue(maxsize=128)
        self.min_utterance_ms = min_utterance_ms
        self.endpoint = VadEndpointAccumulator(end_silence_ms=end_silence_ms) if endpointing else None
        self.background_processing = background_processing
        self.stage_logger = stage_logger or (lambda stage, metrics: None)
        self._input = bytearray()
        self._input_rate = 48_000
        self._audio_started = False
        self.dropped_output = 0
        self.dropped_input = 0
        self._closed = False
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True) if background_processing else None
        if self._worker:
            self._worker.start()

    def _record_processing_error(self, exc: Exception) -> None:
        try:
            self.stage_logger("turn_error", {"error_type": type(exc).__name__})
        except Exception:  # noqa: BLE001 - observability must not kill the worker
            pass

    def _worker_loop(self) -> None:
        while True:
            item = self.input_queue.get()
            if item is None:
                return
            try:
                self._emit(*item)
            except Exception as exc:  # noqa: BLE001 - keep the call worker alive
                self._record_processing_error(exc)

    def _emit(self, pcm: bytes, sample_rate: int) -> None:
        if self._closed:
            return
        self.stage_logger("utterance_ready", {"duration_ms": round(len(pcm) / max(1, sample_rate * 2) * 1000, 2)})
        for output_pcm in self.processor.process_utterance(pcm, sample_rate):
            if not output_pcm or self._closed:
                continue
            try:
                self.output.put_nowait((bytes(output_pcm), 48_000))
                self.stage_logger("outbound_pcm_ready", {"chunks": self.output.qsize(), "pcm_bytes": len(output_pcm)})
            except queue.Full:
                self.dropped_output += 1

    def _submit(self, pcm: bytes, sample_rate: int) -> None:
        if not self.background_processing:
            self._emit(pcm, sample_rate)
            return
        try:
            self.input_queue.put_nowait((pcm, sample_rate))
        except queue.Full:
            self.dropped_input += 1

    def on_pcm(self, pcm: bytes, sample_rate: int) -> None:
        if not pcm or self._closed:
            return
        if not self._audio_started:
            self._audio_started = True
            self.stage_logger("inbound_audio_started", {"sample_rate": sample_rate})
        if self.endpoint is not None:
            for utterance in self.endpoint.push(pcm, sample_rate):
                self._submit(utterance, sample_rate)
            return
        if self.min_utterance_ms <= 0:
            self._submit(pcm, sample_rate)
            return
        self._input_rate = sample_rate
        self._input.extend(pcm)
        threshold = max(2, int(sample_rate * 2 * self.min_utterance_ms / 1000))
        while len(self._input) >= threshold and not self._closed:
            chunk = bytes(self._input[:threshold])
            del self._input[:threshold]
            self._submit(chunk, sample_rate)

    def flush(self) -> None:
        if self.endpoint is not None:
            for utterance in self.endpoint.flush():
                self._submit(utterance, self._input_rate)
            return
        if self._input and not self._closed:
            chunk = bytes(self._input)
            self._input.clear()
            self._submit(chunk, self._input_rate)

    def next_output(self, timeout: float = 0.1) -> tuple[bytes, int] | None:
        try:
            item = self.output.get(timeout=timeout)
            self.stage_logger("outbound_pcm_forwarded", {"queue_depth": self.output.qsize(), "pcm_bytes": len(item[0])})
            return item
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
            if self._worker:
                try:
                    self.input_queue.put_nowait(None)
                except queue.Full:
                    pass
        if self._worker:
            self._worker.join(timeout=5)


async def consume_remote_audio_track(track, listeners: Iterable[Callable[[bytes, int], None]]) -> None:
    """Consume aiortc audio until normal remote closure without an unhandled task."""
    try:
        while True:
            frame = await track.recv()
            pcm = frame.to_ndarray().tobytes()
            for listener in listeners:
                listener(pcm, frame.sample_rate or 48_000)
    except Exception as exc:
        try:
            from aiortc.mediastreams import MediaStreamError
        except ImportError:
            MediaStreamError = ()
        if MediaStreamError and isinstance(exc, MediaStreamError):
            return
        raise


class LiveCallingCoordinator:
    """Accepts a verified normalized connect and attaches the duplex bridge."""

    def __init__(self, adapter: WhatsAppCallingAdapter, client: MetaCallingClient, endpoint_factory: Callable[[], WebRtcEndpoint], voice: DuplexVoiceBridge, stage_logger: Callable[[str, dict], None] | None = None):
        self.adapter = adapter
        self.client = client
        self.endpoint_factory = endpoint_factory
        self.voice = voice
        self.stage_logger = stage_logger or (lambda stage, metrics: None)
        self.endpoints: dict[str, WebRtcEndpoint] = {}
        self._workers: dict[str, threading.Thread] = {}
        self._attempts: dict[str, int] = {}

    def _pump_output(self, session_id: str, endpoint: WebRtcEndpoint) -> None:
        while self.endpoints.get(session_id) is endpoint:
            item = self.voice.next_output(timeout=0.2)
            if item is not None:
                try:
                    endpoint.queue_pcm(*item)
                except Exception as exc:
                    self.stage_logger("outbound_pcm_place_error", {"error_type": type(exc).__name__})
                    return

    def _control_stage(self, stage: str, status: str, exc: Exception | None = None) -> None:
        metrics = {"status": status}
        if exc is not None:
            metrics["error_type"] = type(exc).__name__
            if isinstance(exc, CallControlError) and exc.http_status is not None:
                metrics["http_status"] = exc.http_status
        self.stage_logger(f"control_{stage}", metrics)

    def accept_connect(self, envelope: dict) -> dict:
        if envelope.get("kind") != "incoming":
            raise MediaContractError("connect acceptance requires normalized incoming event")
        session = envelope.get("session") or {}
        offer = session.get("sdp")
        if not isinstance(offer, str) or not offer:
            raise MediaContractError("connect event is missing SDP offer")
        call_id = envelope["call_id"]
        result = self.adapter.ingest(envelope)
        if result.get("status") != "accepted":
            return result
        endpoint = None
        stage = "adapter_ingest"
        self._attempts[call_id] = self._attempts.get(call_id, 0) + 1
        self._control_stage(stage, "ok")
        try:
            stage = "sdp_answer"
            endpoint = self.endpoint_factory()
            endpoint.add_pcm_listener(self.voice.on_pcm)
            answer = endpoint.answer(offer)
            self._control_stage(stage, "ok")
            phone_id = envelope["phone_number_id"]
            stage = "pre_accept"
            self.client.send(CallAction(phone_id, call_id, "pre_accept", answer))
            self._control_stage(stage, "ok")
            stage = "accept"
            self.client.send(CallAction(phone_id, call_id, "accept", answer))
            self._control_stage(stage, "ok")
            endpoint_key = result["session_id"]
            if hasattr(self.voice.processor, "session_id"):
                self.voice.processor.session_id = endpoint_key
            self.endpoints[endpoint_key] = endpoint
            worker = threading.Thread(target=self._pump_output, args=(endpoint_key, endpoint), daemon=True)
            self._workers[endpoint_key] = worker
            worker.start()
            self._attempts.pop(call_id, None)
            return {"status": "accepted", "session_id": endpoint_key, "media": "negotiated"}
        except Exception as exc:
            self._control_stage(stage, "error", exc)
            if endpoint is not None:
                try:
                    endpoint.close()
                except Exception as cleanup_exc:
                    self._control_stage("endpoint_cleanup", "error", cleanup_exc)
            try:
                self.adapter.rollback_accept(envelope)
                self._control_stage("rollback", "ok")
            except Exception as rollback_exc:
                self._control_stage("rollback", "error", rollback_exc)
            raise

    def hangup(self, envelope: dict) -> dict:
        result = self.adapter.ingest(envelope)
        sid = result.get("session_id")
        endpoint = self.endpoints.pop(sid, None)
        worker = self._workers.pop(sid, None)
        if endpoint is not None:
            endpoint.close()
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=5)
        self.voice.flush()
        self.voice.close()
        self.stage_logger("teardown_complete", {})
        return result


def aiortc_endpoint_factory(stage_logger: Callable[[str, dict], None] | None = None) -> WebRtcEndpoint:
    """Create the real aiortc endpoint; dependency is intentionally lazy."""
    import asyncio
    try:
        from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
        from av import AudioFrame
    except ImportError as exc:
        raise RuntimeError("aiortc and av are required for live WebRTC media") from exc
    raw_stage_logger = stage_logger or (lambda stage, metrics: None)

    def emit_stage(stage: str, metrics: dict) -> None:
        try:
            raw_stage_logger(stage, metrics)
        except Exception:  # noqa: BLE001 - telemetry must never break media
            pass

    class OutputTrack(MediaStreamTrack):
        kind = "audio"

        def __init__(self):
            super().__init__()
            self.frames: queue.Queue[tuple[bytes, int]] = queue.Queue(maxsize=64)
            self.pending = bytearray()
            self.samples = 0

        async def recv(self):
            frame_bytes = 960 * 2
            loop = asyncio.get_running_loop()
            if self.samples == 0:
                self._started_at = loop.time()
            else:
                target = self._started_at + (self.samples / 48_000)
                await asyncio.sleep(max(0.0, target - loop.time()))

            while len(self.pending) < frame_bytes:
                try:
                    pcm, rate = self.frames.get_nowait()
                except queue.Empty:
                    break
                if rate != 48_000:
                    raise MediaContractError("outbound WebRTC PCM must be 48 kHz")
                self.pending.extend(pcm)
                emit_stage("outbound_pcm_consumed", {"pcm_bytes": len(pcm), "queue_depth": self.frames.qsize()})

            pcm = bytes(self.pending[:frame_bytes])
            del self.pending[:frame_bytes]
            if len(pcm) < frame_bytes:
                pcm += b"\x00" * (frame_bytes - len(pcm))
            frame = AudioFrame(format="s16", layout="mono", samples=960)
            frame.sample_rate = 48_000
            frame.planes[0].update(pcm)
            frame.pts = self.samples
            frame.time_base = __import__("fractions").Fraction(1, 48_000)
            self.samples += frame.samples
            return frame

    class Endpoint:
        def __init__(self):
            self.loop = asyncio.new_event_loop()
            self.ready = threading.Event()
            self.listeners: list[Callable[[bytes, int], None]] = []
            self._track_tasks: set[asyncio.Task] = set()
            self._stats_task: asyncio.Task | None = None
            self._state_lock = threading.Lock()
            self._media_state = {"direction": "unknown", "codec": "unknown"}
            self._closed = False
            self.pc = None
            self.out = None
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            if not self.ready.wait(10):
                raise RuntimeError("aiortc event loop did not start")

        def _run(self):
            asyncio.set_event_loop(self.loop)
            try:
                self.pc = RTCPeerConnection()
                self.out = OutputTrack()
                self.pc.addTrack(self.out)
                self._bind_track()
                self.ready.set()
                self.loop.run_forever()
            finally:
                if not self.ready.is_set():
                    self.ready.set()
                if not self.loop.is_closed():
                    self.loop.run_until_complete(self.loop.shutdown_asyncgens())
                    self.loop.close()

        def _bind_track(self):
            @self.pc.on("track")
            def on_track(track):
                if track.kind != "audio":
                    return
                task = self.loop.create_task(consume_remote_audio_track(track, self.listeners))
                self._track_tasks.add(task)
                task.add_done_callback(self._track_tasks.discard)
                task.add_done_callback(self._consume_track_result)

        @staticmethod
        def _consume_track_result(task):
            if task.cancelled():
                return
            # Retrieving the exception prevents "Task exception was never retrieved"
            # during remote-track failures; the call worker records its own stages.
            task.exception()

        def answer(self, offer_sdp: str) -> str:
            async def negotiate():
                await self.pc.setRemoteDescription(RTCSessionDescription(sdp=offer_sdp, type="offer"))
                answer = await self.pc.createAnswer()
                await self.pc.setLocalDescription(answer)
                transceiver = next((item for item in self.pc.getTransceivers() if item.sender.track is self.out), None)
                direction = (transceiver.currentDirection or transceiver.direction) if transceiver else "unknown"
                local_sdp = self.pc.localDescription.sdp
                lines = local_sdp.splitlines()
                audio_line = next((line for line in lines if line.startswith("m=audio ")), "")
                payloads = audio_line.split()[3:]
                codec_by_payload = {}
                for line in lines:
                    if line.startswith("a=rtpmap:"):
                        payload, encoding = line[len("a=rtpmap:"):].split(None, 1)
                        codec_by_payload[payload] = encoding.split("/", 1)[0].lower()
                codec = codec_by_payload.get(payloads[0], "unknown") if payloads else "unknown"
                with self._state_lock:
                    self._media_state = {"direction": direction, "codec": codec}
                    media_state = self._media_state.copy()
                emit_stage("outbound_media_negotiated", media_state)
                if direction not in {"sendrecv", "sendonly"}:
                    raise MediaContractError("negotiated WebRTC direction does not allow outbound audio")
                return local_sdp
            return asyncio.run_coroutine_threadsafe(negotiate(), self.loop).result(30)

        def add_pcm_listener(self, listener): self.listeners.append(listener)
        def queue_pcm(self, pcm, sample_rate=48_000):
            if sample_rate != 48_000 or len(pcm) % 2:
                raise MediaContractError("outbound WebRTC PCM must be mono signed 16-bit at 48 kHz")
            with self._state_lock:
                if self._closed:
                    raise MediaContractError("outbound WebRTC endpoint is closed")
                self.out.frames.put_nowait((bytes(pcm), sample_rate))
                queue_depth = self.out.frames.qsize()
                if self.loop.is_running():
                    try:
                        self.loop.call_soon_threadsafe(self._schedule_sender_stats)
                    except RuntimeError:
                        pass
            emit_stage("outbound_pcm_placed", {"pcm_bytes": len(pcm), "queue_depth": queue_depth})

        def _schedule_sender_stats(self):
            with self._state_lock:
                if self._closed or (self._stats_task is not None and not self._stats_task.done()):
                    return
                task = self.loop.create_task(self._report_sender_stats_after_delay())
                self._stats_task = task
            task.add_done_callback(self._finish_sender_stats)

        def _finish_sender_stats(self, task):
            with self._state_lock:
                if self._stats_task is task:
                    self._stats_task = None
            self._consume_track_result(task)

        async def _collect_sender_stats(self):
            report = await self.pc.getStats()
            outbound = [item for item in report.values() if item.type == "outbound-rtp" and getattr(item, "kind", None) == "audio"]
            return {
                "packets_sent": sum(int(getattr(item, "packetsSent", 0)) for item in outbound),
                "bytes_sent": sum(int(getattr(item, "bytesSent", 0)) for item in outbound),
            }

        async def _report_sender_stats_after_delay(self):
            await asyncio.sleep(0.12)
            with self._state_lock:
                if self._closed:
                    return {}
            metrics = await self._collect_sender_stats()
            emit_stage("outbound_rtp_stats", metrics)
            return metrics

        def media_state(self):
            with self._state_lock:
                return self._media_state.copy()

        def sender_stats(self):
            with self._state_lock:
                if self._closed:
                    raise MediaContractError("outbound WebRTC endpoint is closed")
            metrics = asyncio.run_coroutine_threadsafe(self._collect_sender_stats(), self.loop).result(10)
            emit_stage("outbound_rtp_stats", metrics)
            return metrics

        def close(self):
            with self._state_lock:
                if self._closed:
                    return
                self._closed = True

            async def shutdown():
                with self._state_lock:
                    stats_task = self._stats_task
                pending_tasks = set(self._track_tasks)
                if stats_task is not None:
                    pending_tasks.add(stats_task)
                for task in tuple(pending_tasks):
                    task.cancel()
                if pending_tasks:
                    await asyncio.gather(*pending_tasks, return_exceptions=True)
                if self.pc is not None:
                    await self.pc.close()

            if self.thread.is_alive():
                future = asyncio.run_coroutine_threadsafe(shutdown(), self.loop)
                future.result(10)
                self.loop.call_soon_threadsafe(self.loop.stop)
                self.thread.join(timeout=10)

    return Endpoint()
