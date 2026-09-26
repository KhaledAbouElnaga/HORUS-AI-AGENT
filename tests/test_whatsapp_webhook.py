import hashlib
import hmac
import json

import pytest

from horus_local_voice.whatsapp_calling import WhatsAppCallingAdapter
from horus_local_voice.whatsapp_webhook import (
    CALLBACK_PATH,
    WebhookAuthError,
    WhatsAppCallingWebhook,
)


class Runtime:
    def open_session(self, session_id): pass
    def ingest_media(self, session_id, media): pass
    def cancel(self, session_id): pass
    def close_session(self, session_id): pass


def test_callback_path_and_get_verification():
    webhook = WhatsAppCallingWebhook(WhatsAppCallingAdapter(Runtime()), lambda p: [])
    assert webhook.path == CALLBACK_PATH
    assert webhook.verify_get({"hub.mode": "subscribe", "hub.verify_token": "local-token", "hub.challenge": "123"}, "local-token").body == "123"
    with pytest.raises(WebhookAuthError):
        webhook.verify_get({"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "123"}, "local-token")


def test_post_requires_valid_meta_signature_before_parser():
    called = []
    webhook = WhatsAppCallingWebhook(WhatsAppCallingAdapter(Runtime()), lambda p: called.append(p) or [])
    body = json.dumps({"object": "whatsapp_business_account"}).encode()
    secret = "test-app-secret"
    digest = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert webhook.receive_post(body, digest, secret) == []
    assert called
    with pytest.raises(WebhookAuthError):
        webhook.receive_post(body, "sha256=bad", secret)


def test_meta_dashboard_calls_sample_parses_connect_and_terminate():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "waba-redacted", "changes": [{"field": "calls", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": "phone-redacted"},
            "contacts": [{"user_id": "user-redacted"}],
            "calls": [{"id": "wacid.sample", "from_user_id": "user-redacted", "event": "connect", "timestamp": "1", "session": {"sdp_type": "offer", "sdp": "v=0"}}]
        }}]}]
    }
    from horus_local_voice.whatsapp_webhook import parse_meta_calls_payload
    events = parse_meta_calls_payload(payload)
    assert len(events) == 1
    assert events[0]["kind"] == "incoming"
    assert events[0]["call_id"] == "wacid.sample"
    assert events[0]["session"]["sdp_type"] == "offer"

    payload["entry"][0]["changes"][0]["value"]["calls"][0]["event"] = "terminate"
    events = parse_meta_calls_payload(payload)
    assert events[0]["kind"] == "hangup"


def test_runner_log_is_redacted_to_timestamp_kind_and_status():
    from scripts.run_whatsapp_webhook_server import redacted_event_log
    line = redacted_event_log("incoming", "accepted")
    assert "timestamp=" in line and "kind=incoming" in line and "status=accepted" in line
    assert not any(secret in line for secret in ("call-", "user-", "phone-", "sdp", "SDP", "sha256"))


def test_meta_parser_runs_only_after_signature_validation():
    called = []
    webhook = WhatsAppCallingWebhook(WhatsAppCallingAdapter(Runtime()), lambda p: called.append(p) or [])
    body = b'{"object":"whatsapp_business_account"}'
    with pytest.raises(WebhookAuthError):
        webhook.receive_post(body, "sha256=invalid", "app-secret")
    assert called == []
