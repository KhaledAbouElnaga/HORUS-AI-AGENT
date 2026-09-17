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
