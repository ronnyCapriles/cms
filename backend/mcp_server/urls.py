from django.urls import path

from . import oauth, protocol

urlpatterns = [
    # Both forms: APPEND_SLASH would 301 a slashless POST, dropping its body.
    path("mcp", protocol.endpoint, name="mcp-endpoint"),
    path("mcp/", protocol.endpoint),

    path(".well-known/oauth-protected-resource", oauth.protected_resource,
         name="mcp-protected-resource"),
    path(".well-known/oauth-protected-resource/mcp", oauth.protected_resource),
    path(".well-known/oauth-authorization-server", oauth.authorization_server,
         name="mcp-authorization-server"),
    path(".well-known/oauth-authorization-server/mcp", oauth.authorization_server),

    path("oauth/register", oauth.register, name="mcp-oauth-register"),
    path("oauth/authorize", oauth.authorize, name="mcp-oauth-authorize"),
    path("oauth/token", oauth.token, name="mcp-oauth-token"),
    path("oauth/revoke", oauth.revoke, name="mcp-oauth-revoke"),
]
