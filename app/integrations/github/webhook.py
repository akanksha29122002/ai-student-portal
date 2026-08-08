"""GitHub webhook utilities — signature verification and event parsing."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging

from app.integrations.github.schemas import PushEvent

logger = logging.getLogger("project_defense.integrations.github.webhook")


def verify_signature(body: bytes, signature_header: str | None, secret: str) -> bool:
    """Verify GitHub's ``X-Hub-Signature-256`` HMAC header.

    Returns ``False`` (rather than raising) when the signature is missing or
    the secret is empty, so callers can respond with 401 gracefully.

    Uses ``hmac.compare_digest`` to prevent timing attacks.
    """
    if not signature_header or not secret:
        return False
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    expected = f"sha256={mac.hexdigest()}"
    return hmac.compare_digest(expected, signature_header)


def parse_push_event(body: bytes) -> PushEvent:
    """Parse a raw push-event webhook body into a ``PushEvent``."""
    data = json.loads(body)
    return PushEvent.model_validate(data)
