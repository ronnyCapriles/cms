"""A minimal OAuth 2.1 authorization server, for clients that accept only a URL.

Discovery starts from the 401 the MCP endpoint returns. Consent runs behind
staff_member_required, so the admin login decides who may approve a client.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .models import (
    McpAuthorizationCode, McpClient, McpToken, Scope, hash_secret, new_secret,
)

CODE_TTL = timedelta(minutes=5)
ACCESS_TTL = timedelta(days=int(getattr(settings, "MCP_ACCESS_TOKEN_DAYS", 30)))
REFRESH_TTL = timedelta(days=int(getattr(settings, "MCP_REFRESH_TOKEN_DAYS", 365)))


def base_url(request) -> str:
    return request.build_absolute_uri("/").rstrip("/")


def protected_resource_metadata_url(request) -> str:
    return request.build_absolute_uri("/.well-known/oauth-protected-resource")


def _json(payload, status=200) -> JsonResponse:
    response = JsonResponse(payload, status=status)
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    response["Cache-Control"] = "public, max-age=3600"
    return response


def _error(code, description, status=400) -> JsonResponse:
    return _json({"error": code, "error_description": description}, status=status)


@require_GET
def protected_resource(request):
    """RFC 9728: this resource, and where to get a token for it."""
    root = base_url(request)
    return _json({
        "resource": f"{root}/mcp",
        "authorization_servers": [root],
        "scopes_supported": [Scope.READ, Scope.WRITE],
        "bearer_methods_supported": ["header"],
    })


@require_GET
def authorization_server(request):
    """RFC 8414."""
    root = base_url(request)
    return _json({
        "issuer": root,
        "authorization_endpoint": root + reverse("mcp-oauth-authorize"),
        "token_endpoint": root + reverse("mcp-oauth-token"),
        "registration_endpoint": root + reverse("mcp-oauth-register"),
        "revocation_endpoint": root + reverse("mcp-oauth-revoke"),
        "scopes_supported": [Scope.READ, Scope.WRITE],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    })


@csrf_exempt
@require_POST
def register(request):
    """RFC 7591. Registration is open; approval happens at /oauth/authorize."""
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return _error("invalid_client_metadata", "Body must be JSON.")

    redirect_uris = body.get("redirect_uris") or []
    if not isinstance(redirect_uris, list) or not redirect_uris:
        return _error("invalid_redirect_uri", "redirect_uris must be a non-empty list.")
    for uri in redirect_uris:
        if not _valid_redirect(uri):
            return _error("invalid_redirect_uri", f"{uri} must be https or loopback.")

    client = McpClient.objects.create(
        client_id=new_secret("client"),
        client_name=str(body.get("client_name") or "")[:160],
        redirect_uris=redirect_uris,
    )
    return _json({
        "client_id": client.client_id,
        "client_name": client.client_name,
        "redirect_uris": client.redirect_uris,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "client_id_issued_at": int(client.created_at.timestamp()),
    }, status=201)


def _valid_redirect(uri: str) -> bool:
    try:
        parsed = urlparse(uri)
    except ValueError:
        return False
    if parsed.scheme == "https":
        return True
    # Loopback is the standard exemption for desktop clients.
    return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "::1", "localhost")


@csrf_protect
@staff_member_required
def authorize(request):
    """The consent screen. An anonymous browser is sent to the admin login first."""
    params = request.POST if request.method == "POST" else request.GET

    client = McpClient.objects.filter(client_id=params.get("client_id", "")).first()
    if client is None:
        return _bad_request("Unknown client_id.")

    redirect_uri = params.get("redirect_uri", "")
    if redirect_uri not in client.redirect_uris:
        return _bad_request("redirect_uri does not match the registered client.")

    state = params.get("state", "")
    if params.get("response_type") != "code":
        return _redirect_error(redirect_uri, "unsupported_response_type", state)
    if params.get("code_challenge_method") != "S256":
        return _redirect_error(redirect_uri, "invalid_request",
                               state, "PKCE with S256 is required.")

    challenge = params.get("code_challenge", "")
    if not challenge:
        return _redirect_error(redirect_uri, "invalid_request", state,
                               "code_challenge is required.")

    scope = Scope.READ if params.get("scope") == Scope.READ else Scope.WRITE
    resource = params.get("resource", "")

    if request.method == "GET":
        return render(request, "mcp_server/authorize.html", {
            "client": client,
            "scope": scope,
            "scope_label": "read and write" if scope == Scope.WRITE else "read only",
            "params": {
                "client_id": client.client_id, "redirect_uri": redirect_uri,
                "response_type": "code", "state": state,
                "code_challenge": challenge, "code_challenge_method": "S256",
                "scope": scope, "resource": resource,
            },
        })

    if params.get("decision") != "allow":
        return _redirect_error(redirect_uri, "access_denied", state)

    raw = new_secret("code")
    McpAuthorizationCode.objects.create(
        code_hash=hash_secret(raw), client=client, user=request.user,
        redirect_uri=redirect_uri, code_challenge=challenge, scope=scope,
        resource=resource, expires_at=timezone.now() + CODE_TTL,
    )
    query = {"code": raw}
    if state:
        query["state"] = state
    return HttpResponseRedirect(f"{redirect_uri}?{urlencode(query)}")


def _bad_request(message):
    return HttpResponse(message, status=400, content_type="text/plain")


def _redirect_error(redirect_uri, code, state, description=""):
    query = {"error": code}
    if description:
        query["error_description"] = description
    if state:
        query["state"] = state
    return HttpResponseRedirect(f"{redirect_uri}?{urlencode(query)}")


@csrf_exempt
@require_POST
def token(request):
    grant = request.POST.get("grant_type")
    if grant == "authorization_code":
        return _exchange_code(request)
    if grant == "refresh_token":
        return _refresh(request)
    return _error("unsupported_grant_type", f"grant_type {grant!r} is not supported.")


def _exchange_code(request):
    raw = request.POST.get("code", "")
    record = McpAuthorizationCode.objects.select_related("client", "user").filter(
        code_hash=hash_secret(raw)
    ).first()

    if record is None:
        return _error("invalid_grant", "Unknown authorization code.")
    if record.used_at or record.expires_at <= timezone.now():
        return _error("invalid_grant", "This code was already used or has expired.")
    if record.client.client_id != request.POST.get("client_id"):
        return _error("invalid_grant", "The code was issued to a different client.")
    if record.redirect_uri != request.POST.get("redirect_uri"):
        return _error("invalid_grant", "redirect_uri does not match the request.")

    verifier = request.POST.get("code_verifier", "")
    if _s256(verifier) != record.code_challenge:
        return _error("invalid_grant", "code_verifier does not match code_challenge.")

    record.used_at = timezone.now()
    record.save(update_fields=["used_at"])

    return _issue(
        label=f"{record.client.client_name or record.client.client_id}",
        client=record.client, user=record.user, scope=record.scope,
        resource=record.resource,
    )


def _refresh(request):
    raw = request.POST.get("refresh_token", "")
    token = McpToken.objects.select_related("client", "user").filter(
        refresh_hash=hash_secret(raw), kind=McpToken.OAUTH
    ).first()

    if token is None or token.revoked_at:
        return _error("invalid_grant", "Unknown or revoked refresh token.")
    if token.refresh_expires_at and token.refresh_expires_at <= timezone.now():
        return _error("invalid_grant", "The refresh token has expired.")
    if token.client and token.client.client_id != request.POST.get("client_id"):
        return _error("invalid_grant", "Issued to a different client.")

    # Rotation: issuing a new pair revokes this one.
    token.revoked_at = timezone.now()
    token.save(update_fields=["revoked_at"])

    return _issue(label=token.label, client=token.client, user=token.user,
                  scope=token.scope, resource=token.resource)


def _issue(label, client, user, scope, resource):
    access_raw = new_secret("mcp")
    refresh_raw = new_secret("refresh")
    now = timezone.now()

    McpToken.objects.create(
        label=label[:120], kind=McpToken.OAUTH, scope=scope,
        token_hash=hash_secret(access_raw), refresh_hash=hash_secret(refresh_raw),
        client=client, user=user, resource=resource,
        expires_at=now + ACCESS_TTL, refresh_expires_at=now + REFRESH_TTL,
    )

    return _json({
        "access_token": access_raw,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TTL.total_seconds()),
        "refresh_token": refresh_raw,
        "scope": scope,
    })


@csrf_exempt
@require_POST
def revoke(request):
    raw = request.POST.get("token", "")
    digest = hash_secret(raw)
    McpToken.objects.filter(token_hash=digest).update(revoked_at=timezone.now())
    McpToken.objects.filter(refresh_hash=digest).update(revoked_at=timezone.now())
    # RFC 7009: revocation always reports success.
    return _json({})


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")
