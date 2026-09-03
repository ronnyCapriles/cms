"""The tool registry. Importing this module registers every tool."""
from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import Callable

from django.http import HttpRequest

from ..models import McpToken, Scope


class ToolError(Exception):
    """A failure the agent should read and act on, not a protocol error."""


@dataclass
class Context:
    request: HttpRequest
    token: McpToken


@dataclass
class ToolSpec:
    name: str
    title: str
    description: str
    schema: dict
    fn: Callable
    scope: str
    destructive: bool
    idempotent: bool


REGISTRY: dict[str, ToolSpec] = {}


def tool(name, title, description, schema, scope=Scope.WRITE,
         destructive=False, idempotent=False):
    def register(fn):
        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        schema.setdefault("additionalProperties", False)
        REGISTRY[name] = ToolSpec(
            name=name, title=title,
            # Reaches the model verbatim, so the source indentation comes off.
            description=textwrap.dedent(description).strip(), schema=schema,
            fn=fn, scope=scope, destructive=destructive, idempotent=idempotent,
        )
        return fn

    return register


from . import assets, metrics, projects, read, translations  # noqa: E402,F401
