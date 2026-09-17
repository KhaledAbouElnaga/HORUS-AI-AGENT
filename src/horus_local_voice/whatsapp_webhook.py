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


def parse_meta_calls_payload(payload: dict) -> list[dict]:
    """Parse Meta's documented ``object/entry/changes/value/calls`` shape.

    Only user-initiated non-SIP ``connect`` and ``terminate`` notifications are
    mapped. SDP is passed ephemerally to the channel boundary and never exposed
    by redacted observability.
    """
    if payload.get("object") != "whatsapp_business_account":
        raise WebhookPayloadError("unexpected webhook object")
    result: list[dict] = []
    for entry in payload.get("entry", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("changes"), list):
            raise WebhookPayloadError("entry.changes must be a list")
        waba_id = entry.get("id")
        if not isinstance(waba_id, str) or not waba_id:
            raise WebhookPayloadError("entry.id is required")
        for change in entry["changes"]:
            if not isinstance(change, dict) or change.get("field") != "calls":
                continue
            value = change.get("value")
            if not isinstance(value, dict) or value.get("messaging_product") != "whatsapp":
                raise WebhookPayloadError("calls change has invalid value")
            metadata = value.get("metadata")
            if not isinstance(metadata, dict) or not isinstance(metadata.get("phone_number_id"), str):
                raise WebhookPayloadError("calls metadata.phone_number_id is required")
            contacts = value.get("contacts") or []
            contact = contacts[0] if contacts and isinstance(contacts[0], dict) else {}
            contact_user = contact.get("user_id")
            for call in value.get("calls", []):
                if not isinstance(call, dict) or not isinstance(call.get("id"), str):
                    raise WebhookPayloadError("call.id is required")
                event = call.get("event")
                kind = {"connect": "incoming", "terminate": "hangup"}.get(event)
                if kind is None:
                    raise WebhookPayloadError(f"unsupported calls event: {event}")
                user_id = call.get("from_user_id") or contact_user or call.get("from")
                if not isinstance(user_id, str) or not user_id:
                    raise WebhookPayloadError("call user identity is required")
                session = call.get("session") if isinstance(call.get("session"), dict) else {}
                result.append({
                    "event_id": f"{call['id']}:{event}:{call.get('timestamp', '')}",
                    "kind": kind,
                    "call_id": call["id"],
                    "user_id": user_id,
                    "phone_number_id": metadata["phone_number_id"],
                    "waba_id": waba_id,
                    "timestamp": call.get("timestamp"),
                    "direction": call.get("direction"),
                    "session": {"sdp_type": session.get("sdp_type"), "sdp": session.get("sdp")} if session else None,
                })
    return result


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
        return [{"kind": event["kind"], **self.adapter.ingest(event)} for event in envelopes]
