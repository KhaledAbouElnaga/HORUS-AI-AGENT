"""OpenAI Realtime speech bridge for the existing WhatsApp PCM/RTP boundary.

The bridge deliberately owns no WhatsApp or aiortc logic. It accepts the proven
48 kHz mono PCM boundary, streams 24 kHz PCM to a server-side Realtime
WebSocket, and returns 48 kHz mono PCM to the existing OutputTrack queue.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Protocol


REALTIME_MODEL = "gpt-realtime-2.1"


@dataclass(frozen=True)
class RealtimeTimeouts:
    connect: float = 10.0
    first_response: float = 12.0
    tool: float = 5.0
    response: float = 30.0


class RealtimeTransport(Protocol):
    async def connect(self) -> None: ...
    async def send(self, event: dict) -> None: ...
    async def recv(self) -> dict: ...
    async def close(self) -> None: ...


class OpenAIRealtimeTransport:
    """Thin server-side WebSocket adapter over the official OpenAI SDK."""

    def __init__(self, api_key: str, model: str = REALTIME_MODEL):
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for realtime voice")
        self._api_key = api_key
        self.model = model
        self._client = None
        self._manager = None
        self._connection = None

    async def connect(self) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - exercised by deployment preflight
            raise RuntimeError("openai realtime dependency is not installed") from exc
        self._client = AsyncOpenAI(api_key=self._api_key)
        self._api_key = ""
        self._manager = self._client.realtime.connect(model=self.model, max_retries=0)
        self._connection = await self._manager.__aenter__()

    async def send(self, event: dict) -> None:
        if self._connection is None:
            raise RuntimeError("realtime websocket is not connected")
        await self._connection.send(event)

    async def recv(self) -> dict:
        if self._connection is None:
            raise RuntimeError("realtime websocket is not connected")
        event = await self._connection.recv()
        if isinstance(event, dict):
            return event
        if hasattr(event, "model_dump"):
            return event.model_dump(mode="json", by_alias=True, exclude_none=True)
        raise RuntimeError("unsupported realtime event type")

    async def close(self) -> None:
        connection, client = self._connection, self._client
        self._connection = None
        self._manager = None
        self._client = None
        if connection is not None:
            try:
                await connection.close()
            except Exception:  # noqa: BLE001 - cleanup is best effort
                pass
        if client is not None:
            try:
                await client.close()
            except Exception:  # noqa: BLE001 - cleanup is best effort
                pass


class RealtimeVoiceBridge:
    """One-call Realtime session with bounded I/O, tools, and cleanup."""

    FALLBACK_AR = "حصل عطل مؤقت، جرّب مرة تانية."
    INSTRUCTIONS = (
        "أنت حورس (HORUS)، المساعد الشخصي الذكي لخالد (Khaled). "
        "اتكلم بالمصري بشكل طبيعي وواضح ومختصر ومباشر ومناسب للمكالمة الصوتية. "
        "لو المتصل اتكلم عربي رد بالعربي، ولو اتكلم إنجليزي رد بالإنجليزي. "
        "عرّف نفسك باسم حورس عند السؤال عن اسمك. "
        "استخدم أدوات حورس المحلية للبيانات الحالية بدل التخمين، ولا تكشف تفاصيل التنفيذ الداخلية إلا لو اتطلبت. "
        "خلي الرد غالبًا جملة أو جملتين ومن غير مقدمات طويلة."
    )

    def __init__(
        self,
        session_id: str,
        tool_runtime,
        transport_factory: Callable[[], RealtimeTransport] | None = None,
        stage_logger: Callable[[str, dict], None] | None = None,
        model: str = REALTIME_MODEL,
        voice: str = "marin",
        timeouts: RealtimeTimeouts | None = None,
        max_output_chunks: int = 128,
        playback_tail_ms: int = 600,
    ):
        if not session_id:
            raise ValueError("session_id is required")
        self.session_id = session_id
        self.tool_runtime = tool_runtime
        self.model = model
        self.voice = voice
        self.timeouts = timeouts or RealtimeTimeouts()
        self.stage_logger = stage_logger or (lambda stage, metrics: None)
        self.transport_factory = transport_factory or (
            lambda: OpenAIRealtimeTransport(os.environ.get("OPENAI_API_KEY", ""), model=self.model)
        )
        self.output: queue.Queue[tuple[bytes, int]] = queue.Queue(maxsize=max_output_chunks)
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._thread_main,
            name=f"horus-realtime-{session_id[-12:]}",
            daemon=True,
        )
        self._ready = threading.Event()
        self._start_error: Exception | None = None
        self._transport: RealtimeTransport | None = None
        self._audio_queue = None
        self._stop = None
        self._tool_tasks: set[asyncio.Task] = set()
        self._tool_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="horus-realtime-tool")
        self._closed = False
        self._started = False
        self._lock = threading.Lock()
        self._resample_lock = threading.Lock()
        self._input_resample_state = None
        self._output_resample_state = None
        self._playback_until = 0.0
        self.playback_tail_s = max(0, playback_tail_ms) / 1000.0
        self._audio_input_started = False
        self._turn_ended_at: float | None = None
        self._response_started_at: float | None = None
        self._first_audio_at: float | None = None
        self._response_deadline_at: float | None = None
        self._fallback_requested = False
        self._transcripts: list[str] = []
        self._last_transcript = ""
        self._last_tool_summary: dict[str, object] = {}
        self._tool_started_at: float | None = None
        self._handled_calls: set[str] = set()
        self._metrics: dict[str, object] = {
            "session_ready": False,
            "closed": False,
            "committed_turns": 0,
            "responses_started": 0,
            "responses_completed": 0,
            "audio_input_bytes_24k": 0,
            "audio_output_bytes_24k": 0,
            "audio_forwarded_bytes_48k": 0,
            "tool_calls": 0,
            "tool_results": 0,
            "connect_ms": None,
            "turn_to_first_audio_ms": None,
            "tool_round_trip_ms": None,
            "response_completion_ms": None,
        }

    def _stage(self, stage: str, metrics: dict | None = None) -> None:
        try:
            self.stage_logger(stage, metrics or {})
        except Exception:  # noqa: BLE001 - telemetry must not break media
            pass

    def _session_update(self) -> dict:
        tools = []
        categories = getattr(self.tool_runtime, "realtime_tool_categories", frozenset())
        if "status" in categories:
            tools.append({
                "type": "function",
                "name": "get_horus_status",
                "description": "Read the current local HORUS service status and active task count.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            })
        return {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": self.model,
                "instructions": self.INSTRUCTIONS,
                "output_modalities": ["audio"],
                "max_output_tokens": 220,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": 24_000},
                        "noise_reduction": {"type": "far_field"},
                        "turn_detection": {
                            "type": "semantic_vad",
                            "eagerness": "medium",
                            "create_response": True,
                            "interrupt_response": False,
                        },
                    },
                    "output": {
                        "format": {"type": "audio/pcm", "rate": 24_000},
                        "voice": self.voice,
                    },
                },
                "tools": tools,
                "tool_choice": "auto",
            },
        }

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("realtime bridge is closed")
            if self._started:
                return
            self._started = True
            self._thread.start()
        if not self._ready.wait(self.timeouts.connect + 1.0):
            self.close()
            raise TimeoutError("realtime session startup timed out")
        if self._start_error is not None:
            error = self._start_error
            self.close()
            raise RuntimeError("realtime session startup failed") from error

    def _thread_main(self) -> None:
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._run())
        finally:
            if not self.loop.is_closed():
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
                self.loop.close()

    async def _send_event(self, event: dict, timeout: float | None = None) -> None:
        if self._transport is None:
            raise RuntimeError("realtime websocket is not connected")
        limit = timeout if timeout is not None else max(0.25, min(5.0, self.timeouts.connect))
        await asyncio.wait_for(self._transport.send(event), timeout=limit)

    async def _run(self) -> None:
        self._audio_queue = asyncio.Queue(maxsize=200)
        self._stop = asyncio.Event()
        started = time.perf_counter()
        try:
            self._stage("realtime_connect", {"status": "started"})
            self._transport = self.transport_factory()
            deadline = self.loop.time() + self.timeouts.connect

            def remaining() -> float:
                value = deadline - self.loop.time()
                if value <= 0:
                    raise TimeoutError("realtime session setup timed out")
                return value

            await asyncio.wait_for(self._transport.connect(), timeout=remaining())
            while True:
                event = await asyncio.wait_for(self._transport.recv(), timeout=remaining())
                if event.get("type") == "session.created":
                    break
                await self._handle_event(event)
            await self._send_event(self._session_update(), timeout=remaining())
            while True:
                event = await asyncio.wait_for(self._transport.recv(), timeout=remaining())
                if event.get("type") == "session.updated":
                    break
                await self._handle_event(event)
            connect_ms = round((time.perf_counter() - started) * 1000, 2)
            with self._lock:
                self._metrics["connect_ms"] = connect_ms
                self._metrics["session_ready"] = True
            self._stage("realtime_session_ready", {"elapsed_ms": connect_ms, "model": self.model})
            self._ready.set()
            sender = asyncio.create_task(self._audio_sender(), name="realtime-audio-sender")
            receiver = asyncio.create_task(self._receiver(), name="realtime-receiver")
            stop_waiter = asyncio.create_task(self._stop.wait(), name="realtime-stop")
            done, pending = await asyncio.wait({sender, receiver, stop_waiter}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                if task is not stop_waiter and not task.cancelled():
                    exc = task.exception()
                    if exc is not None:
                        raise exc
        except Exception as exc:  # noqa: BLE001 - convert backend failure to a safe stage
            if not self._ready.is_set():
                self._start_error = exc
                self._ready.set()
            stage = "realtime_timeout" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else "realtime_error"
            self._stage(stage, {"error_type": type(exc).__name__})
        finally:
            for task in list(self._tool_tasks):
                task.cancel()
            if self._tool_tasks:
                await asyncio.gather(*self._tool_tasks, return_exceptions=True)
            if self._transport is not None:
                await self._transport.close()
            with self._lock:
                self._metrics["session_ready"] = False
            self._ready.set()

    async def _audio_sender(self) -> None:
        while not self._stop.is_set():
            pcm24 = await self._audio_queue.get()
            if pcm24 is None:
                return
            await self._send_event({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm24).decode("ascii"),
            })
            with self._lock:
                self._metrics["audio_input_bytes_24k"] += len(pcm24)

    async def _receiver(self) -> None:
        while not self._stop.is_set():
            try:
                event = await asyncio.wait_for(self._transport.recv(), timeout=0.2)
            except asyncio.TimeoutError:
                await self._check_deadlines()
                continue
            await self._handle_event(event)
            await self._check_deadlines()

    async def _handle_event(self, event: dict) -> None:
        kind = event.get("type", "")
        now = time.perf_counter()
        if kind == "input_audio_buffer.speech_started":
            self._fallback_requested = False
        elif kind == "input_audio_buffer.speech_stopped":
            self._turn_ended_at = now
            self._first_audio_at = None
            self._response_started_at = None
        elif kind == "input_audio_buffer.committed":
            with self._lock:
                self._metrics["committed_turns"] += 1
            self._stage("realtime_turn_committed", {})
        elif kind == "response.created":
            self._response_started_at = now
            self._response_deadline_at = now + self.timeouts.response
            self._transcripts.clear()
            with self._lock:
                self._metrics["responses_started"] += 1
            self._stage("realtime_response_started", {})
        elif kind in {"response.output_audio.delta", "response.audio.delta"}:
            await self._handle_audio_delta(event, now)
        elif kind in {"response.output_audio_transcript.done", "response.audio_transcript.done"}:
            transcript = event.get("transcript")
            if isinstance(transcript, str) and transcript:
                self._transcripts.append(transcript)
        elif kind == "response.output_item.done":
            item = event.get("item") or {}
            if item.get("type") == "function_call":
                self._schedule_tool(item)
        elif kind == "response.function_call_arguments.done":
            item = {
                "type": "function_call",
                "name": event.get("name"),
                "call_id": event.get("call_id"),
                "arguments": event.get("arguments", "{}"),
            }
            self._schedule_tool(item)
        elif kind == "response.done":
            response = event.get("response") or {}
            status = response.get("status")
            if status not in {None, "completed"}:
                self._response_deadline_at = None
                self._stage("realtime_error", {"error_type": "response_failed"})
                await self._request_fallback()
                return
            started = self._response_started_at
            elapsed = round((now - started) * 1000, 2) if started is not None else None
            with self._lock:
                self._metrics["responses_completed"] += 1
                self._metrics["response_completion_ms"] = elapsed
                if self._transcripts:
                    self._last_transcript = " ".join(self._transcripts)
            self._response_deadline_at = None
            self._stage("realtime_response_complete", {"elapsed_ms": elapsed or 0.0})
        elif kind == "error":
            error = event.get("error") or {}
            self._stage("realtime_error", {"error_type": str(error.get("type") or "api_error")})
            await self._request_fallback()

    async def _handle_audio_delta(self, event: dict, now: float) -> None:
        encoded = event.get("delta")
        if not isinstance(encoded, str) or not encoded:
            return
        try:
            pcm24 = base64.b64decode(encoded, validate=True)
        except Exception:
            self._stage("realtime_error", {"error_type": "invalid_audio_delta"})
            return
        if not pcm24 or len(pcm24) % 2:
            self._stage("realtime_error", {"error_type": "invalid_pcm16"})
            return
        pcm48 = self._resample_pcm16(pcm24, 24_000, 48_000, output=True)
        if not pcm48:
            return
        try:
            self.output.put_nowait((pcm48, 48_000))
        except queue.Full:
            self._stage("realtime_error", {"error_type": "output_queue_full"})
            return
        first = self._first_audio_at is None
        if first:
            self._first_audio_at = now
            elapsed = round((now - self._turn_ended_at) * 1000, 2) if self._turn_ended_at is not None else 0.0
            with self._lock:
                self._metrics["turn_to_first_audio_ms"] = elapsed
            self._stage("realtime_first_audio", {"elapsed_ms": elapsed})
        with self._lock:
            self._metrics["audio_output_bytes_24k"] += len(pcm24)

    def _schedule_tool(self, item: dict) -> None:
        call_id = item.get("call_id")
        if not isinstance(call_id, str) or not call_id or call_id in self._handled_calls:
            return
        self._handled_calls.add(call_id)
        task = asyncio.create_task(self._handle_tool(item), name="realtime-tool")
        self._tool_tasks.add(task)
        task.add_done_callback(self._tool_tasks.discard)

    async def _handle_tool(self, item: dict) -> None:
        started = time.perf_counter()
        name = item.get("name")
        call_id = item.get("call_id")
        self._stage("realtime_tool_call", {"tool": str(name or "unknown")})
        try:
            if name != "get_horus_status":
                raise PermissionError("unsupported realtime tool")
            raw_arguments = item.get("arguments") or "{}"
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            if not isinstance(arguments, dict):
                raise ValueError("tool arguments must be an object")
            loop = asyncio.get_running_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    self._tool_executor,
                    self.tool_runtime.invoke_realtime_tool,
                    self.session_id,
                    "status",
                    arguments,
                ),
                timeout=self.timeouts.tool,
            )
            output = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
            await self._send_event({"type": "conversation.item.create", "item": {"type": "function_call_output", "call_id": call_id, "output": output}})
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            with self._lock:
                self._metrics["tool_calls"] += 1
                self._metrics["tool_results"] += 1
                self._metrics["tool_round_trip_ms"] = elapsed
                self._last_tool_summary = {
                    "category": "status",
                    "service": result.get("service") if isinstance(result, dict) else None,
                    "ready": result.get("ready") if isinstance(result, dict) else None,
                    "active_tasks": result.get("active_tasks") if isinstance(result, dict) else None,
                }
            self._stage("realtime_tool_result", {"elapsed_ms": elapsed, "status": "ok"})
            await self._send_event({"type": "response.create"})
        except (TimeoutError, asyncio.TimeoutError):
            with self._lock:
                self._metrics["tool_calls"] += 1
            self._stage("realtime_timeout", {"stage": "tool", "error_type": "TimeoutError"})
            await self._request_fallback()
        except Exception as exc:  # noqa: BLE001 - send no internal details to caller/log
            with self._lock:
                self._metrics["tool_calls"] += 1
            self._stage("realtime_error", {"stage": "tool", "error_type": type(exc).__name__})
            await self._request_fallback()

    async def _check_deadlines(self) -> None:
        now = time.perf_counter()
        if self._turn_ended_at is not None and self._first_audio_at is None:
            if now - self._turn_ended_at > self.timeouts.first_response:
                self._turn_ended_at = None
                self._stage("realtime_timeout", {"stage": "first_response", "error_type": "TimeoutError"})
                await self._request_fallback()
        if self._response_deadline_at is not None and now > self._response_deadline_at:
            self._response_deadline_at = None
            self._stage("realtime_timeout", {"stage": "response", "error_type": "TimeoutError"})
            await self._request_fallback()

    async def _request_fallback(self) -> None:
        with self._lock:
            ready = bool(self._metrics["session_ready"])
        if self._fallback_requested or self._transport is None or not ready:
            return
        self._fallback_requested = True
        try:
            await self._send_event({"type": "response.cancel"})
        except Exception:
            pass
        try:
            await self._send_event({
                "type": "response.create",
                "response": {
                    "output_modalities": ["audio"],
                    "instructions": f'قل فقط بالمصري: "{self.FALLBACK_AR}"',
                    "max_output_tokens": 40,
                },
            })
        except Exception as exc:  # noqa: BLE001
            self._stage("realtime_error", {"stage": "fallback", "error_type": type(exc).__name__})

    @staticmethod
    def _audioop_ratecv(pcm: bytes, source_rate: int, target_rate: int, state):
        try:
            import audioop
        except ImportError as exc:  # pragma: no cover - production runtime is Python 3.12
            raise RuntimeError("PCM16 resampling requires Python 3.12 audioop") from exc
        return audioop.ratecv(pcm, 2, 1, source_rate, target_rate, state)

    def _resample_pcm16(self, pcm: bytes, source_rate: int, target_rate: int, *, output: bool) -> bytes:
        if source_rate == target_rate:
            return pcm
        with self._resample_lock:
            state = self._output_resample_state if output else self._input_resample_state
            converted, state = self._audioop_ratecv(pcm, source_rate, target_rate, state)
            if output:
                self._output_resample_state = state
            else:
                self._input_resample_state = state
            return converted

    def on_pcm(self, pcm: bytes, sample_rate: int) -> None:
        if not pcm:
            return
        if sample_rate != 48_000 or len(pcm) % 2:
            raise ValueError("realtime inbound PCM must be mono signed PCM16 at 48 kHz")
        with self._lock:
            if self._closed:
                return
            playback_active = time.monotonic() < self._playback_until
            ready = bool(self._metrics["session_ready"])
        if playback_active:
            self._stage("inbound_suppressed_playback", {"duration_ms": round(self.playback_tail_s * 1000)})
            return
        if not ready or self._audio_queue is None:
            self._stage("realtime_error", {"error_type": "session_not_ready"})
            return
        pcm24 = self._resample_pcm16(pcm, 48_000, 24_000, output=False)
        if not self._audio_input_started:
            self._audio_input_started = True
            self._stage("realtime_audio_input_started", {"sample_rate": 24_000})

        def enqueue() -> None:
            try:
                self._audio_queue.put_nowait(pcm24)
            except asyncio.QueueFull:
                self._stage("realtime_error", {"error_type": "input_queue_full"})

        try:
            self.loop.call_soon_threadsafe(enqueue)
        except RuntimeError:
            self._stage("realtime_error", {"error_type": "session_closed"})

    def on_playout_pcm(self, pcm: bytes, sample_rate: int) -> None:
        if not pcm or not any(pcm):
            return
        with self._lock:
            self._playback_until = time.monotonic() + self.playback_tail_s

    def next_output(self, timeout: float = 0.1) -> tuple[bytes, int] | None:
        try:
            item = self.output.get(timeout=timeout)
        except queue.Empty:
            return None
        with self._lock:
            self._metrics["audio_forwarded_bytes_48k"] += len(item[0])
        self._stage("realtime_audio_forwarded", {"pcm_bytes": len(item[0]), "queue_depth": self.output.qsize()})
        return item

    def flush(self) -> None:
        """Semantic VAD owns turn commit; local shutdown must not invent a turn."""

    def transcript_contains(self, expected: str) -> bool:
        with self._lock:
            return expected in self._last_transcript or any(expected in value for value in tuple(self._transcripts))

    def tool_result_summary(self) -> dict:
        with self._lock:
            return dict(self._last_tool_summary)

    def thread_alive(self) -> bool:
        return self._thread.is_alive()

    def request_status_tool(self) -> None:
        """Preflight hook: force the same advertised read-only tool in-session."""
        async def request() -> None:
            await self._send_event({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "استخدم أداة حالة حورس ثم قل النتيجة باختصار."}],
                },
            })
            await self._send_event({
                "type": "response.create",
                "response": {
                    "output_modalities": ["audio"],
                    "tool_choice": "required",
                    "instructions": "Call get_horus_status exactly once, then speak its result briefly in Arabic.",
                },
            })

        if not self.loop.is_running() or self._transport is None:
            raise RuntimeError("realtime session is not ready")
        future = asyncio.run_coroutine_threadsafe(request(), self.loop)
        future.result(timeout=2.0)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._metrics)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        if not self._started and not self.loop.is_closed():
            self.loop.close()
        elif self.loop.is_running() and self._stop is not None:
            def stop() -> None:
                self._stop.set()
                try:
                    self._audio_queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass
            try:
                self.loop.call_soon_threadsafe(stop)
            except RuntimeError:
                pass
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=max(2.0, self.timeouts.connect + 1.0))
        self._tool_executor.shutdown(wait=False, cancel_futures=True)
        while not self.output.empty():
            try:
                self.output.get_nowait()
            except queue.Empty:
                break
        with self._lock:
            self._metrics["closed"] = True
            self._metrics["session_ready"] = False
