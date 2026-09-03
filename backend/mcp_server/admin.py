"""Tokens are created here. The plaintext is shown once and never stored."""
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import McpAuthorizationCode, McpCall, McpClient, McpToken, hash_secret, new_secret


@admin.register(McpToken)
class McpTokenAdmin(admin.ModelAdmin):
    list_display = ("label", "kind", "scope", "state", "client", "user",
                    "last_used_at", "created_at")
    list_filter = ("kind", "scope", "client")
    search_fields = ("label",)
    readonly_fields = ("token_hash", "refresh_hash", "created_at", "last_used_at",
                       "kind", "client", "resource")
    actions = ["revoke_selected"]
    fields = ("label", "scope", "kind", "user", "client", "resource",
              "expires_at", "revoked_at", "token_hash", "refresh_hash",
              "created_at", "last_used_at")

    @admin.display(description="State")
    def state(self, obj):
        if obj.revoked_at:
            return format_html('<b style="color:#d95f5f">revoked</b>')
        if not obj.active:
            return format_html('<span style="color:#d9a441">expired</span>')
        return format_html('<span style="color:#4fb286">active</span>')

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ("token_hash", "refresh_hash", "created_at", "last_used_at")
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        """Generates the secret on add and shows it once."""
        if not change:
            raw = new_secret("mcp")
            obj.token_hash = hash_secret(raw)
            obj.kind = McpToken.STATIC
            obj.user = obj.user or request.user
            super().save_model(request, obj, form, change)
            messages.warning(
                request,
                format_html(
                    "Copy this token now, it is not stored and cannot be shown "
                    "again:<br><code style='user-select:all'>{}</code>", raw,
                ),
            )
            return
        super().save_model(request, obj, form, change)

    @admin.action(description="Revoke selected tokens")
    def revoke_selected(self, request, queryset):
        updated = queryset.filter(revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        self.message_user(request, f"Revoked {updated} token(s).")


@admin.register(McpClient)
class McpClientAdmin(admin.ModelAdmin):
    list_display = ("client_name", "client_id", "token_count", "created_at")
    search_fields = ("client_name", "client_id")
    readonly_fields = ("client_id", "created_at")

    @admin.display(description="Tokens")
    def token_count(self, obj):
        return obj.tokens.count()


@admin.register(McpCall)
class McpCallAdmin(admin.ModelAdmin):
    list_display = ("created_at", "tool", "ok", "duration_ms", "token")
    list_filter = ("ok", "tool")
    search_fields = ("tool", "error")
    readonly_fields = ("token", "tool", "arguments", "ok", "error", "duration_ms",
                       "created_at")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(McpAuthorizationCode)
class McpAuthorizationCodeAdmin(admin.ModelAdmin):
    list_display = ("client", "user", "created_at", "expires_at", "used_at")
    readonly_fields = [f.name for f in McpAuthorizationCode._meta.fields]

    def has_add_permission(self, request):
        return False
