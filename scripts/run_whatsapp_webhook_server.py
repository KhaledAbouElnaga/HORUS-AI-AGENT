"""Runnable local Meta Calling ingress with live non-SIP media wiring.

All secrets are read only from the environment. Logs are intentionally limited to
startup state and normalized event status; payloads, identifiers, SDP, and secret
values never enter logs.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from horus_local_voice.whatsapp_calling import WhatsAppCallingAdapter
from horus_local_voice.whatsapp_media import (
    DuplexVoiceBridge,
    LiveCallingCoordinator,
    MetaCallingClient,
    PipelineVoiceTurnProcessor,
    aiortc_endpoint_factory,
)
from horus_local_voice.whatsapp_webhook import WhatsAppCallingWebhook, parse_meta_calls_payload

logger = logging.getLogger("whatsapp_calling_live")
logging.basicConfig(level=logging.INFO, format="%(message)s")

LIVE_ENV_NAMES = (
    "WHATSAPP_WEBHOOK_VERIFY_TOKEN",
    "META_APP_SECRET",
    "WHATSAPP_ACCESS_TOKEN",
    "HORUS_ROOT",
    "STT_MODEL",
    "PIPER_AR_VOICE",
    "PIPER_EN_VOICE",
)


class _IngressRuntime:
    """Control adapter for the media bridge; audio is handled by its PCM path."""

    def __init__(self, horus):
        self.horus = horus

    def open_session(self, session_id):
        self.horus.resume_session(session_id)

    def ingest_media(self, session_id, media):
        pass

    def cancel(self, session_id):
        self.horus.cancel(session_id)

    def close_session(self, session_id):
        self.horus.close(session_id)


def _parser(payload: dict) -> list[dict]:
    return parse_meta_calls_payload(payload)


def redacted_event_log(kind: str, status: str) -> str:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"calling_event timestamp={timestamp} kind={kind} status={status}"


def create_live_event_handler(coordinator: LiveCallingCoordinator):
    """Dispatch normalized events after webhook signature validation and parsing."""
    def handle(event: dict) -> dict:
        if event["kind"] == "incoming":
            return coordinator.accept_connect(event)
        if event["kind"] == "hangup":
            return coordinator.hangup(event)
        raise ValueError("unsupported live event kind")
    return handle


def build_live_coordinator() -> LiveCallingCoordinator:
    """Load real STT, HORUS, TTS, Graph control, and aiortc components."""
    missing = [name for name in LIVE_ENV_NAMES if not os.environ.get(name)]
    if missing:
        raise RuntimeError("missing live media environment variables: " + ",".join(missing))
    import numpy as np
    from faster_whisper import WhisperModel
    from piper import PiperVoice
    from horus_local_voice.local_horus_port import LocalHorusPythonPort
    from horus_local_voice.streaming import IncrementalTranscriber, script_route

    model = WhisperModel(os.environ["STT_MODEL"], device="cpu", compute_type=os.environ.get("STT_COMPUTE_TYPE", "int8"))

    def transcribe(pcm: bytes) -> str:
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = model.transcribe(samples, beam_size=1, vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()

    transcriber = IncrementalTranscriber(transcribe, sample_rate=16_000)
    voices = {
        "ar": PiperVoice.load(os.environ["PIPER_AR_VOICE"]),
        "en": PiperVoice.load(os.environ["PIPER_EN_VOICE"]),
    }
    tts_rate = int(os.environ.get("PIPER_TTS_SAMPLE_RATE", "22050"))

    def synthesize(text: str) -> bytes:
        voice = voices[script_route(text)]
        return b"".join(chunk.audio_int16_bytes for chunk in voice.synthesize(text))

    horus = LocalHorusPythonPort(os.environ["HORUS_ROOT"])
    runtime = _IngressRuntime(horus)
    adapter = WhatsAppCallingAdapter(runtime)
    processor = PipelineVoiceTurnProcessor("pending", transcriber, horus, synthesize, tts_sample_rate=tts_rate)
    bridge = DuplexVoiceBridge(processor, max_output_chunks=64, min_utterance_ms=800)
    client = MetaCallingClient(os.environ["WHATSAPP_ACCESS_TOKEN"], api_version=os.environ.get("META_API_VERSION", "v26.0"))
    return LiveCallingCoordinator(adapter, client, aiortc_endpoint_factory, bridge)


# Import-safe ingress object; live handler is attached only in main().
class _NoopRuntime:
    def open_session(self, session_id): pass
    def ingest_media(self, session_id, media): pass
    def cancel(self, session_id): pass
    def close_session(self, session_id): pass


adapter = WhatsAppCallingAdapter(_NoopRuntime())
webhook = WhatsAppCallingWebhook(adapter, _parser)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != webhook.path:
            self.send_error(404)
            return
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        try:
            response = webhook.verify_get(query, os.environ["WHATSAPP_WEBHOOK_VERIFY_TOKEN"])
        except Exception:
            self.send_error(403)
            return
        self.send_response(response.status)
        self.end_headers()
        self.wfile.write(response.body.encode())

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != webhook.path:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        try:
            results = webhook.receive_post(body, self.headers.get("X-Hub-Signature-256"), os.environ["META_APP_SECRET"])
        except Exception:
            logger.info(redacted_event_log("unparsed", "contract_mismatch"))
            self.send_error(403)
            return
        for result in results:
            logger.info(redacted_event_log(result["kind"], result["status"]))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"EVENT_RECEIVED")


def configure_live_media() -> LiveCallingCoordinator:
    coordinator = build_live_coordinator()
    webhook.event_handler = create_live_event_handler(coordinator)
    return coordinator


def main() -> None:
    configure_live_media()
    port = int(os.environ.get("WEBHOOK_PORT", "8788"))
    logger.info("live_calling_server media=enabled port=%d signature_validation=enabled", port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
