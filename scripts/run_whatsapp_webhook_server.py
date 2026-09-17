"""Ephemeral local HTTP wrapper for the prepared Meta webhook route.

It is for reversible external ingress probing only; no Meta payloads or secrets
are persisted. The process reads secrets from environment variables and never
prints them.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from horus_local_voice.whatsapp_calling import WhatsAppCallingAdapter
from horus_local_voice.whatsapp_webhook import WhatsAppCallingWebhook, parse_meta_calls_payload


class _Runtime:
    def open_session(self, session_id): pass
    def ingest_media(self, session_id, media): pass
    def cancel(self, session_id): pass
    def close_session(self, session_id): pass


def _parser(payload: dict) -> list[dict]:
    return parse_meta_calls_payload(payload)


adapter = WhatsAppCallingAdapter(_Runtime())
webhook = WhatsAppCallingWebhook(adapter, _parser)
logger = logging.getLogger("whatsapp_calling_webhook")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def redacted_event_log(kind: str, status: str) -> str:
    """Return the only event fields permitted in runner logs."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"calling_event timestamp={timestamp} kind={kind} status={status}"


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
            results = webhook.receive_post(
                body,
                self.headers.get("X-Hub-Signature-256"),
                os.environ["META_APP_SECRET"],
            )
        except Exception:
            # Signature/payload failures have no normalized event kind.
            logger.info(redacted_event_log("unparsed", "contract_mismatch"))
            self.send_error(403)
            return
        for result in results:
            logger.info(redacted_event_log(result["kind"], result["status"]))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"EVENT_RECEIVED")


if __name__ == "__main__":
    port = int(os.environ.get("WEBHOOK_PORT", "8788"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
