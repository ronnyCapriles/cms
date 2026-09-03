"""JSON-RPC 2.0 over Streamable HTTP: the MCP endpoint.

Stateless: responses are always application/json, with no SSE stream and no
session id, so a request holds a worker thread only while it is answered.
"""
from __future__ import annotations

import json
import time

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .auth import authenticate
from .models import McpCall, Scope
from .tools import REGISTRY, Context, ToolError

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]

SERVER_INFO = {"name": "portfolio-cms", "title": "Portfolio CMS", "version": "1.0.0"}

INSTRUCTIONS = """\
This server edits the content of a portfolio CMS: one site profile, capability
cards, tags, and projects (case studies) that own metrics, metric tables and
media.

Start with describe_content_model. It lists every writable field, every choice
value and the shortcode syntax.

Three things shape how the content works:

1. Bodies place their own blocks. A line reading [[asset:REF]] or
   [[metrics:REF]] in body_md renders that block exactly there. Anything never
   referenced still renders, appended after the body. Creation tools return the
   shortcode to paste.
2. Translations are rows, not fields. Write the original in one language, then
   call set_translation once per field per language. translation_coverage says
   what is still missing.
3. Nothing you create is live. Every new project starts unpublished;
   publish_project is the only way that changes. Ask before publishing.
"""


def rpc_result(request_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def rpc_error(request_id, code, message, data=None) -> dict:
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _cors(response):
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response["Access-Control-Allow-Headers"] = (
        "Authorization, Content-Type, Accept, MCP-Protocol-Version, Mcp-Session-Id"
    )
    response["Access-Control-Expose-Headers"] = "WWW-Authenticate, MCP-Protocol-Version"
    response["Access-Control-Max-Age"] = "86400"
    return response


def unauthorized(request) -> HttpResponse:
    """401 pointing at the resource metadata, which is what starts OAuth discovery."""
    from .oauth import protected_resource_metadata_url

    response = JsonResponse(
        rpc_error(None, -32001, "Unauthorized: a bearer token is required."), status=401
    )
    response["WWW-Authenticate"] = (
        f'Bearer resource_metadata="{protected_resource_metadata_url(request)}"'
    )
    return _cors(response)


def negotiate(requested: str | None) -> str:
    if requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return LATEST_PROTOCOL_VERSION


def tool_descriptors(token) -> list[dict]:
    return [
        {
            "name": spec.name,
            "title": spec.title,
            "description": spec.description,
            "inputSchema": spec.schema,
            "annotations": {
                "readOnlyHint": spec.scope == Scope.READ,
                "destructiveHint": spec.destructive,
                "idempotentHint": spec.idempotent,
            },
        }
        for spec in REGISTRY.values()
        if token.allows(spec.scope)
    ]


def _as_content(payload, ok) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2, default=str)}],
        "isError": not ok,
    }


def call_tool(params, token, request) -> dict:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    spec = REGISTRY.get(name)

    if spec is None:
        return _as_content(
            {"error": f"No such tool: {name!r}.",
             "available": sorted(n for n, s in REGISTRY.items() if token.allows(s.scope))},
            ok=False,
        )
    if not token.allows(spec.scope):
        return _as_content(
            {"error": f"{name} needs write scope; this token is read only."}, ok=False
        )

    started = time.monotonic()
    context = Context(request=request, token=token)
    error = ""
    try:
        if spec.scope == Scope.WRITE:
            with transaction.atomic():
                payload = spec.fn(arguments, context)
        else:
            payload = spec.fn(arguments, context)
        ok = True
    except ToolError as exc:
        payload, ok, error = {"error": str(exc)}, False, str(exc)
    except Exception as exc:
        payload, ok = {"error": f"{type(exc).__name__}: {exc}"}, False
        error = payload["error"]

    _audit(token, name, arguments, ok, error, time.monotonic() - started)

    return _as_content(payload, ok)


def _audit(token, name, arguments, ok, error, seconds):
    try:
        McpCall.objects.create(
            token=token, tool=name, arguments=arguments, ok=ok,
            error=error[:2000], duration_ms=int(seconds * 1000),
        )
    except Exception:
        # An audit failure must not turn a successful edit into an error.
        pass


def dispatch(message, token, request):
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if method == "initialize":
        return rpc_result(request_id, {
            "protocolVersion": negotiate(params.get("protocolVersion")),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": INSTRUCTIONS,
        })

    if method == "ping":
        return rpc_result(request_id, {})

    if method == "tools/list":
        return rpc_result(request_id, {"tools": tool_descriptors(token)})

    if method == "tools/call":
        return rpc_result(request_id, call_tool(params, token, request))

    # Not advertised, but clients probe for them.
    if method in ("resources/list", "resources/templates/list"):
        return rpc_result(request_id, {"resources": [], "resourceTemplates": []})
    if method == "prompts/list":
        return rpc_result(request_id, {"prompts": []})

    return rpc_error(request_id, -32601, f"Method not found: {method}")


@csrf_exempt
def endpoint(request):
    if request.method == "OPTIONS":
        return _cors(HttpResponse(status=204))

    if request.method == "GET":
        # No server-initiated stream.
        return _cors(HttpResponse(status=405))

    if request.method != "POST":
        return _cors(HttpResponse(status=405))

    token = authenticate(request)
    if token is None:
        return unauthorized(request)

    try:
        message = json.loads(request.body or b"{}")
    except ValueError:
        return _cors(JsonResponse(rpc_error(None, -32700, "Parse error"), status=400))

    if isinstance(message, list):
        return _cors(JsonResponse(
            rpc_error(None, -32600, "Batched requests are not supported."), status=400,
        ))
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _cors(JsonResponse(
            rpc_error(None, -32600, "Invalid request"), status=400,
        ))

    # A notification carries no id and gets no response body.
    if "id" not in message:
        return _cors(HttpResponse(status=202))

    response = JsonResponse(dispatch(message, token, request))
    response["MCP-Protocol-Version"] = negotiate(
        request.headers.get("MCP-Protocol-Version")
    )
    return _cors(response)
