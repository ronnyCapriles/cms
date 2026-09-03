"""Bearer authentication for the MCP endpoint.

Cookies are not accepted: the endpoint is CSRF exempt, so a session credential
here would make it a cross-site write API.
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .models import McpToken, hash_secret

# A write per call would take the SQLite write lock on every read.
TOUCH_INTERVAL = timedelta(minutes=5)


def bearer(request) -> str | None:
    header = request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def authenticate(request) -> McpToken | None:
    raw = bearer(request)
    if not raw:
        return None

    digest = hash_secret(raw)
    token = McpToken.objects.filter(token_hash=digest).select_related("user").first()
    if token is None or not token.active:
        return None

    now = timezone.now()
    if token.last_used_at is None or now - token.last_used_at > TOUCH_INTERVAL:
        McpToken.objects.filter(pk=token.pk).update(last_used_at=now)

    return token
