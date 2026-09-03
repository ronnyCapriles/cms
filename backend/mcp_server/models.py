"""Credentials and audit for the MCP endpoint.

Secrets are stored as SHA-256 digests; the plaintext is shown once, at creation.
"""
from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

TOKEN_BYTES = 32


def new_secret(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(TOKEN_BYTES)}"


def hash_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class Scope(models.TextChoices):
    READ = "read", "Read only"
    WRITE = "write", "Read and write"


class McpClient(models.Model):
    """A client that registered itself (RFC 7591). Registration is open; a
    client is inert until a staff user approves it at /oauth/authorize."""

    client_id = models.CharField(max_length=64, unique=True)
    client_name = models.CharField(max_length=160, blank=True)
    redirect_uris = models.JSONField(default=list)
    scope = models.CharField(max_length=10, choices=Scope.choices, default=Scope.WRITE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "OAuth client"

    def __str__(self) -> str:
        return self.client_name or self.client_id


class McpToken(models.Model):
    """A bearer credential, either a hand-made token or an OAuth grant."""

    STATIC = "static"
    OAUTH = "oauth"
    KIND = [(STATIC, "Personal token"), (OAUTH, "OAuth grant")]

    label = models.CharField(max_length=120, help_text="What this token is for.")
    kind = models.CharField(max_length=10, choices=KIND, default=STATIC)
    scope = models.CharField(max_length=10, choices=Scope.choices, default=Scope.WRITE)

    token_hash = models.CharField(max_length=64, unique=True)
    refresh_hash = models.CharField(max_length=64, unique=True, blank=True, null=True)

    client = models.ForeignKey(
        McpClient, related_name="tokens", on_delete=models.CASCADE, blank=True, null=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="mcp_tokens", on_delete=models.CASCADE,
        blank=True, null=True, help_text="Whose authority the token acts with.",
    )
    resource = models.CharField(max_length=300, blank=True)

    expires_at = models.DateTimeField(blank=True, null=True)
    refresh_expires_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "MCP token"

    def __str__(self) -> str:
        return f"{self.label} ({self.get_scope_display()})"

    @property
    def active(self) -> bool:
        if self.revoked_at:
            return False
        return not (self.expires_at and self.expires_at <= timezone.now())

    def allows(self, needed: str) -> bool:
        return self.scope == Scope.WRITE or needed == Scope.READ


class McpAuthorizationCode(models.Model):
    """One-shot authorization code, held as a row so it cannot be replayed."""

    code_hash = models.CharField(max_length=64, unique=True)
    client = models.ForeignKey(McpClient, related_name="codes", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    redirect_uri = models.CharField(max_length=500)
    code_challenge = models.CharField(max_length=200)
    scope = models.CharField(max_length=10, choices=Scope.choices, default=Scope.WRITE)
    resource = models.CharField(max_length=300, blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"code for {self.client}"


class McpCall(models.Model):
    """One tool invocation, kept for audit."""

    token = models.ForeignKey(
        McpToken, related_name="calls", on_delete=models.SET_NULL, blank=True, null=True,
    )
    tool = models.CharField(max_length=80)
    arguments = models.JSONField(default=dict, blank=True)
    ok = models.BooleanField(default=True)
    error = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"]), models.Index(fields=["tool"])]
        verbose_name = "MCP call"

    def __str__(self) -> str:
        return f"{self.tool} {'ok' if self.ok else 'failed'}"


def issue_token(label, scope=Scope.WRITE, kind=McpToken.STATIC, **extra) -> tuple[McpToken, str]:
    """Returns the token and its plaintext, which is not stored."""
    raw = new_secret("mcp")
    token = McpToken.objects.create(
        label=label, scope=scope, kind=kind, token_hash=hash_secret(raw), **extra
    )
    return token, raw
