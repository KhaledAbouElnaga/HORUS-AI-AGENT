"""Meta webhook verification and non-SIP Calling ingress boundary.

This is framework-neutral so it can be mounted at the prepared route without
choosing a hosting provider or touching production. It never stores the verify
or app secret. The actual Meta payload is forwarded to an injected parser only
after authenticity checks.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Callable, Mapping

from .whatsapp_calling import WhatsAppCallingAdapter

CALLBACK_PATH = "/webhooks/whatsapp/calling"
VERIFY_TOKEN_ENV = "WHATSAPP_WEBHOOK_VERIFY_TOKEN"
SIGNATURE_HEADER = "X-Hub-Signature-256"


class WebhookAuthError(ValueError):
    pass


class WebhookPayloadError(ValueError):
    pass


@dataclass(frozen=True)
class WebhookResponse:
    status: int
    body: str


class WhatsAppCallingWebhook:
    """Prepared GET verification and POST ingress for the non-SIP path."""

    path = CALLBACK_PATH

    def __init__(self, adapter: WhatsAppCallingAdapter, event_parser: Callable[[dict], list[dict]]):
        self.adapter = adapter
        self.event_parser = event_parser

    @staticmethod
    def verify_get(query: Mapping[str, str], configured_verify_token: str) -> WebhookResponse:
        if query.get("hub.mode") != "subscribe":
            raise WebhookAuthError("hub.mode must be subscribe")
        supplied = query.get("hub.verify_token", "")
        if not configured_verify_token or not hmac.compare_digest(supplied, configured_verify_token):
            raise WebhookAuthError("verify token mismatch")
        challenge = query.get("hub.challenge")
        if challenge is None:
            raise WebhookAuthError("missing hub.challenge")
        return WebhookResponse(200, challenge)

    @staticmethod
    def verify_signature(raw_body: bytes, signature: str | None, app_secret: str) -> None:
        if not signature or not signature.startswith("sha256=") or not app_secret:
            raise WebhookAuthError("missing signature or app secret")
        expected = "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise WebhookAuthError("invalid webhook signature")

    def receive_post(self, raw_body: bytes, signature: str | None, app_secret: str) -> list[dict]:
        self.verify_signature(raw_body, signature, app_secret)
        try:
            payload = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WebhookPayloadError("body is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise WebhookPayloadError("body must be a JSON object")
        envelopes = self.event_parser(payload)
        if not isinstance(envelopes, list):
            raise WebhookPayloadError("event parser must return a list")
        return [self.adapter.ingest(event) for event in envelopes]
