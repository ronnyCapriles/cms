"""Smoke tests for the protocol, the tool surface and the OAuth flow."""
from __future__ import annotations

import base64
import hashlib
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from portfolio.models import Project, SiteProfile, Tag

from .models import McpClient, Scope, issue_token


def s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


class McpTestCase(TestCase):
    def setUp(self):
        _, self.write_token = issue_token("test write", Scope.WRITE)
        _, self.read_token = issue_token("test read", Scope.READ)

    def rpc(self, method, params=None, token=None, request_id=1):
        body = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            body["params"] = params
        response = self.client.post(
            "/mcp", data=json.dumps(body), content_type="application/json",
            headers={"authorization": f"Bearer {token or self.write_token}"},
        )
        return response

    def call(self, name, arguments=None, token=None):
        response = self.rpc("tools/call", {"name": name, "arguments": arguments or {}},
                            token=token)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["result"]
        payload = json.loads(result["content"][0]["text"])
        return payload, result.get("isError", False)

    def ok(self, name, arguments=None, token=None):
        payload, is_error = self.call(name, arguments, token)
        self.assertFalse(is_error, payload)
        return payload

    def fails(self, name, arguments=None, token=None):
        payload, is_error = self.call(name, arguments, token)
        self.assertTrue(is_error, payload)
        return payload


class TransportTests(McpTestCase):
    def test_unauthenticated_gets_401_pointing_at_resource_metadata(self):
        response = self.client.post("/mcp", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)
        self.assertIn("resource_metadata=", response["WWW-Authenticate"])

    def test_bad_token_is_rejected(self):
        response = self.rpc("ping", token="mcp_not-a-real-token")
        self.assertEqual(response.status_code, 401)

    def test_get_is_not_a_stream(self):
        response = self.client.get(
            "/mcp", headers={"authorization": f"Bearer {self.write_token}"}
        )
        self.assertEqual(response.status_code, 405)

    def test_slashed_and_slashless_both_answer(self):
        for path in ("/mcp", "/mcp/"):
            response = self.client.post(
                path, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
                content_type="application/json",
                headers={"authorization": f"Bearer {self.write_token}"},
            )
            self.assertEqual(response.status_code, 200, path)

    def test_spa_catch_all_does_not_swallow_the_endpoint(self):
        response = self.client.post("/mcp", data="{}", content_type="application/json")
        self.assertEqual(response["Content-Type"], "application/json")

    def test_initialize_negotiates_and_carries_instructions(self):
        result = self.rpc("initialize", {"protocolVersion": "2025-03-26"}).json()["result"]
        self.assertEqual(result["protocolVersion"], "2025-03-26")
        self.assertIn("tools", result["capabilities"])
        self.assertIn("[[asset:REF]]", result["instructions"])

    def test_unknown_protocol_version_falls_back_to_latest(self):
        result = self.rpc("initialize", {"protocolVersion": "1999-01-01"}).json()["result"]
        self.assertEqual(result["protocolVersion"], "2025-06-18")

    def test_notification_gets_no_body(self):
        response = self.client.post(
            "/mcp",
            data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            content_type="application/json",
            headers={"authorization": f"Bearer {self.write_token}"},
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.content, b"")

    def test_unknown_method(self):
        body = self.rpc("does/not/exist").json()
        self.assertEqual(body["error"]["code"], -32601)

    def test_malformed_json(self):
        response = self.client.post(
            "/mcp", data="{nope", content_type="application/json",
            headers={"authorization": f"Bearer {self.write_token}"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], -32700)


class ScopeTests(McpTestCase):
    def test_read_token_sees_only_read_tools(self):
        listed = self.rpc("tools/list", token=self.read_token).json()["result"]["tools"]
        names = {t["name"] for t in listed}
        self.assertIn("list_projects", names)
        self.assertNotIn("create_project", names)
        self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in listed))

    def test_write_token_sees_everything(self):
        listed = self.rpc("tools/list").json()["result"]["tools"]
        names = {t["name"] for t in listed}
        self.assertIn("create_project", names)
        self.assertIn("list_projects", names)

    def test_read_token_cannot_write(self):
        payload = self.fails(
            "create_project",
            {"title": "X", "summary": "y", "year": 2026},
            token=self.read_token,
        )
        self.assertIn("read only", payload["error"])

    def test_every_tool_has_a_usable_schema(self):
        for spec in self.rpc("tools/list").json()["result"]["tools"]:
            self.assertEqual(spec["inputSchema"]["type"], "object", spec["name"])
            self.assertTrue(spec["description"], spec["name"])


class ProjectToolTests(McpTestCase):
    def test_create_is_never_published_and_publish_is_separate(self):
        created = self.ok("create_project", {
            "title": "Streaming CDC pipeline", "summary": "Kafka to Iceberg.",
            "year": 2026, "domain": "streaming",
        })
        self.assertFalse(created["published"])
        self.assertEqual(created["slug"], "streaming-cdc-pipeline")
        self.assertFalse(Project.objects.get(slug=created["slug"]).published)

        self.ok("publish_project", {"slug": created["slug"]})
        self.assertTrue(Project.objects.get(slug=created["slug"]).published)

        self.ok("unpublish_project", {"slug": created["slug"]})
        self.assertFalse(Project.objects.get(slug=created["slug"]).published)

    def test_published_cannot_be_set_through_update(self):
        self.ok("create_project", {"title": "A", "summary": "b", "year": 2026})
        payload = self.fails("update_project", {"slug": "a", "fields": {"published": True}})
        self.assertIn("published", json.dumps(payload))
        self.assertFalse(Project.objects.get(slug="a").published)

    def test_duplicate_slug_is_refused_not_suffixed(self):
        self.ok("create_project", {"title": "Same", "summary": "b", "year": 2026})
        payload = self.fails("create_project",
                             {"title": "Same", "summary": "c", "year": 2026})
        self.assertIn("already uses the slug", payload["error"])
        self.assertEqual(Project.objects.filter(slug="same").count(), 1)

    def test_retitling_keeps_the_slug(self):
        self.ok("create_project", {"title": "Old name", "summary": "b", "year": 2026})
        self.ok("update_project", {"slug": "old-name", "fields": {"title": "New name"}})
        project = Project.objects.get(slug="old-name")
        self.assertEqual(project.title, "New name")

    def test_update_reports_only_what_changed(self):
        self.ok("create_project", {"title": "T", "summary": "s", "year": 2026})
        result = self.ok("update_project",
                         {"slug": "t", "fields": {"summary": "s", "role": "Lead"}})
        self.assertEqual(result["changed"], ["role"])

    def test_unknown_field_names_the_writable_set(self):
        self.ok("create_project", {"title": "T", "summary": "s", "year": 2026})
        payload = self.fails("update_project", {"slug": "t", "fields": {"nope": 1}})
        self.assertIn("nope", payload["error"])

    def test_missing_project_lists_known_slugs(self):
        self.ok("create_project", {"title": "Findable", "summary": "s", "year": 2026})
        payload = self.fails("get_project", {"slug": "ghost"})
        self.assertIn("findable", payload["error"])

    def test_tags_must_exist_unless_asked_to_create(self):
        payload = self.fails("create_project", {
            "title": "T", "summary": "s", "year": 2026, "tags": ["kafka"],
        })
        self.assertIn("create_tag", payload["error"])

        created = self.ok("create_project", {
            "title": "T", "summary": "s", "year": 2026,
            "tags": ["Kafka"], "create_missing_tags": True,
        })
        self.assertEqual(created["tags"], ["kafka"])
        self.assertEqual(created["tags_created"], ["kafka"])

    def test_set_project_tags_replaces(self):
        self.ok("create_project", {"title": "T", "summary": "s", "year": 2026})
        Tag.objects.create(name="Flink")
        Tag.objects.create(name="Iceberg")
        self.ok("set_project_tags", {"slug": "t", "tags": ["flink", "iceberg"]})
        self.ok("set_project_tags", {"slug": "t", "tags": ["flink"]})
        self.assertEqual(
            list(Project.objects.get(slug="t").tags.values_list("slug", flat=True)),
            ["flink"],
        )

    def test_list_projects_filters_compose(self):
        self.ok("create_project", {"title": "One", "summary": "s", "year": 2025,
                                   "domain": "batch"})
        self.ok("create_project", {"title": "Two", "summary": "s", "year": 2026,
                                   "domain": "streaming"})
        self.ok("publish_project", {"slug": "two"})

        self.assertEqual(self.ok("list_projects", {})["count"], 2)
        self.assertEqual(self.ok("list_projects", {"published": False})["count"], 1)
        self.assertEqual(self.ok("list_projects", {"domain": "batch"})["count"], 1)
        self.assertEqual(self.ok("list_projects", {"year": 2026})["count"], 1)
        self.assertEqual(self.ok("list_projects", {"q": "One"})["count"], 1)


class EmbedTests(McpTestCase):
    def setUp(self):
        super().setUp()
        self.ok("create_project", {"title": "Case", "summary": "s", "year": 2026})

    def test_asset_shortcode_places_the_block(self):
        asset = self.ok("create_asset",
                        {"project": "case", "kind": "image", "ref": "architecture"})
        self.assertEqual(asset["shortcode"], "[[asset:architecture]]")

        self.ok("update_project", {"slug": "case", "fields": {
            "body_md": f"## Design\n\n{asset['shortcode']}\n\nAfter the diagram.",
        }})

        preview = self.ok("render_preview", {"slug": "case"})
        self.assertIn("asset:architecture", preview["placed"])
        self.assertEqual(preview["unresolved_shortcodes"], [])
        self.assertEqual([t["title"] for t in preview["toc"]], ["Design"])

    def test_unresolved_shortcode_is_reported_not_swallowed(self):
        self.ok("update_project",
                {"slug": "case", "fields": {"body_md": "[[asset:typo]]"}})
        preview = self.ok("render_preview", {"slug": "case"})
        self.assertEqual(preview["unresolved_shortcodes"], ["[[asset:typo]]"])

    def test_metric_group_round_trip(self):
        first = self.ok("create_metric", {"project": "case", "label": "p99",
                                          "value": "42s", "ref": "p99"})
        second = self.ok("create_metric", {"project": "case", "label": "Cost",
                                           "value": "-38%", "ref": "cost"})
        group = self.ok("create_metric_group", {
            "project": "case", "layout": "table", "ref": "impact",
            "metric_refs": [first["ref"], second["ref"]],
        })
        self.assertEqual(group["shortcode"], "[[metrics:impact]]")
        self.assertEqual(group["metric_refs"], ["p99", "cost"])

        reordered = self.ok("set_group_metrics", {
            "project": "case", "ref": "impact", "metric_refs": ["cost", "p99"],
        })
        self.assertEqual(reordered["metric_refs"], ["cost", "p99"])

        self.ok("update_project", {"slug": "case", "fields": {
            "body_md": "Numbers:\n\n[[metrics:impact]]\n",
        }})
        preview = self.ok("render_preview", {"slug": "case"})
        self.assertIn("metrics:impact", preview["placed"])
        self.assertIn("-38%", preview["html"])

    def test_a_metric_cannot_appear_twice_in_a_table(self):
        metric = self.ok("create_metric",
                         {"project": "case", "label": "L", "value": "1", "ref": "m1"})
        self.ok("create_metric_group",
                {"project": "case", "layout": "table", "ref": "g1"})
        payload = self.fails("set_group_metrics", {
            "project": "case", "ref": "g1", "metric_refs": [metric["ref"], metric["ref"]],
        })
        self.assertIn("only appear once", payload["error"])

    def test_metrics_cannot_cross_projects(self):
        self.ok("create_project", {"title": "Other", "summary": "s", "year": 2026})
        stranger = self.ok("create_metric",
                           {"project": "other", "label": "L", "value": "1"})
        self.ok("create_metric_group",
                {"project": "case", "layout": "table", "ref": "g"})
        payload = self.fails("set_group_metrics", {
            "project": "case", "ref": "g", "metric_refs": [stranger["ref"]],
        })
        self.assertIn("another project", payload["error"])

    def test_changing_a_ref_warns_that_bodies_break(self):
        self.ok("create_asset", {"project": "case", "kind": "image", "ref": "old"})
        result = self.ok("update_asset",
                         {"project": "case", "ref": "old", "fields": {"ref": "new"}})
        self.assertIn("[[asset:old]]", result["warning"])

    def test_project_source_reports_placement(self):
        self.ok("create_asset", {"project": "case", "kind": "image", "ref": "placed"})
        self.ok("create_asset", {"project": "case", "kind": "image", "ref": "loose"})
        self.ok("update_project",
                {"slug": "case", "fields": {"body_md": "[[asset:placed]]"}})

        source = self.ok("get_project", {"slug": "case"})
        placement = {a["ref"]: a["placed_in_body"] for a in source["assets"]}
        self.assertEqual(placement, {"placed": True, "loose": False})
        self.assertEqual(source["body_md"], "[[asset:placed]]")


class UploadTests(McpTestCase):
    ONE_PIXEL_PNG = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )

    def test_upload_attaches_a_file_to_an_asset(self):
        self.ok("create_project", {"title": "Case", "summary": "s", "year": 2026})
        self.ok("create_asset", {"project": "case", "kind": "image", "ref": "shot"})

        result = self.ok("upload_media", {
            "target": "asset_image", "project": "case", "ref": "shot",
            "filename": "shot.png", "content_base64": self.ONE_PIXEL_PNG,
        })
        self.assertTrue(result["stored"])

        source = self.ok("get_project", {"slug": "case"})
        self.assertTrue(source["assets"][0]["has_file"])

    def test_bad_base64_is_a_readable_error(self):
        self.ok("create_project", {"title": "Case", "summary": "s", "year": 2026})
        self.ok("create_asset", {"project": "case", "kind": "image", "ref": "shot"})
        payload = self.fails("upload_media", {
            "target": "asset_image", "project": "case", "ref": "shot",
            "filename": "x.png", "content_base64": "not base64!!",
        })
        self.assertIn("base64", payload["error"])

    def test_presign_says_so_when_media_is_local(self):
        payload = self.fails("presign_upload", {"filename": "big.mp4"})
        self.assertIn("upload_media", payload["error"])


class TranslationTests(McpTestCase):
    def setUp(self):
        super().setUp()
        self.ok("create_project", {
            "title": "Pipeline", "summary": "Kafka to Iceberg.", "year": 2026,
        })

    def test_set_and_clear_a_translation(self):
        result = self.ok("set_translation", {
            "model": "project", "identifier": "pipeline", "lang": "es",
            "field": "title", "value": "Tubería",
        })
        self.assertTrue(result["saved"])

        project = Project.objects.get(slug="pipeline")
        self.assertEqual(project.tr("title", "es"), "Tubería")
        self.assertEqual(project.tr("title", "en"), "Pipeline")

        self.ok("set_translation", {
            "model": "project", "identifier": "pipeline", "lang": "es",
            "field": "title", "value": "",
        })
        self.assertEqual(
            Project.objects.get(slug="pipeline").tr("title", "es"), "Pipeline"
        )

    def test_translating_into_the_source_language_is_refused(self):
        payload = self.fails("set_translation", {
            "model": "project", "identifier": "pipeline", "lang": "en",
            "field": "title", "value": "x",
        })
        self.assertIn("already written in en", payload["error"])

    def test_untranslatable_field_lists_the_translatable_ones(self):
        payload = self.fails("set_translation", {
            "model": "project", "identifier": "pipeline", "lang": "es",
            "field": "year", "value": "2026",
        })
        self.assertIn("body_md", payload["error"])

    def test_coverage_tracks_what_is_missing(self):
        before = self.ok("translation_coverage", {"slug": "pipeline"})
        self.assertFalse(before["complete"])
        missing = before["incomplete"][0]["missing"]
        self.assertIn("title", missing)
        self.assertIn("summary", missing)

        for field in missing:
            self.ok("set_translation", {
                "model": "project", "identifier": "pipeline", "lang": "es",
                "field": field, "value": f"es-{field}",
            })
        self.assertTrue(self.ok("translation_coverage", {"slug": "pipeline"})["complete"])

    def test_asset_ref_needs_a_project_when_ambiguous(self):
        self.ok("create_project", {"title": "Other", "summary": "s", "year": 2026})
        self.ok("create_asset", {"project": "pipeline", "kind": "image", "ref": "same"})
        self.ok("create_asset", {"project": "other", "kind": "image", "ref": "same"})

        payload = self.fails("set_translation", {
            "model": "asset", "identifier": "same", "lang": "es",
            "field": "caption", "value": "x",
        })
        self.assertIn("More than one", payload["error"])

        self.ok("set_translation", {
            "model": "asset", "identifier": "same", "project": "pipeline",
            "lang": "es", "field": "caption", "value": "Diagrama",
        })


class ProfileTests(McpTestCase):
    def test_missing_profile_says_so(self):
        payload = self.fails("get_site_profile")
        self.assertIn("Django admin", payload["error"])

    def test_update_profile(self):
        SiteProfile.objects.create(name="Ronny", role="Data Engineer",
                                   hero_quote="Move the data.")
        result = self.ok("update_site_profile",
                         {"fields": {"location": "Caracas", "email": "a@b.com"}})
        self.assertEqual(sorted(result["changed"]), ["email", "location"])
        self.assertEqual(SiteProfile.objects.get().location, "Caracas")

    def test_capability_round_trip(self):
        created = self.ok("create_capability", {
            "title": "Ingestion & CDC", "body": "Kafka, Debezium.",
            "tools": "Kafka, Debezium, Flink",
        })
        self.assertEqual(created["tools"], ["Kafka", "Debezium", "Flink"])
        self.ok("update_capability", {"id": created["id"], "fields": {"order": 3}})
        listed = {c["id"]: c for c in self.ok("list_capabilities")["results"]}
        self.assertEqual(listed[created["id"]]["order"], 3)


class DeleteTests(McpTestCase):
    def test_confirm_must_match(self):
        self.ok("create_project", {"title": "Keep", "summary": "s", "year": 2026})
        payload = self.fails("delete_content", {
            "model": "project", "identifier": "keep", "confirm": "yes",
        })
        self.assertIn("Nothing was deleted", payload["error"])
        self.assertTrue(Project.objects.filter(slug="keep").exists())

    def test_deleting_a_project_takes_its_children(self):
        self.ok("create_project", {"title": "Doomed", "summary": "s", "year": 2026})
        self.ok("create_asset", {"project": "doomed", "kind": "image"})
        self.ok("create_metric", {"project": "doomed", "label": "L", "value": "1"})

        result = self.ok("delete_content", {
            "model": "project", "identifier": "doomed", "confirm": "doomed",
        })
        self.assertGreaterEqual(result["deleted"], 3)
        self.assertFalse(Project.objects.filter(slug="doomed").exists())


class AuditTests(McpTestCase):
    def test_calls_are_recorded_including_failures(self):
        from .models import McpCall

        self.ok("create_project", {"title": "Logged", "summary": "s", "year": 2026})
        self.fails("get_project", {"slug": "ghost"})

        self.assertTrue(McpCall.objects.filter(tool="create_project", ok=True).exists())
        failure = McpCall.objects.get(tool="get_project")
        self.assertFalse(failure.ok)
        self.assertIn("ghost", failure.error)

    def test_a_failed_write_leaves_nothing_behind(self):
        self.fails("create_project", {"title": "T", "summary": "s", "year": 2026,
                                      "tags": ["missing"]})
        self.assertFalse(Project.objects.filter(slug="t").exists())


class OAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("ronny", "r@example.com", "pw")

    def test_protected_resource_metadata_points_at_this_server(self):
        body = self.client.get("/.well-known/oauth-protected-resource").json()
        self.assertTrue(body["resource"].endswith("/mcp"))
        self.assertEqual(body["bearer_methods_supported"], ["header"])

    def test_metadata_is_served_at_the_suffixed_path_too(self):
        self.assertEqual(
            self.client.get("/.well-known/oauth-protected-resource/mcp").status_code, 200
        )
        self.assertEqual(
            self.client.get("/.well-known/oauth-authorization-server/mcp").status_code, 200
        )

    def test_authorization_server_metadata_requires_pkce(self):
        body = self.client.get("/.well-known/oauth-authorization-server").json()
        self.assertEqual(body["code_challenge_methods_supported"], ["S256"])
        self.assertIn("/oauth/register", body["registration_endpoint"])

    def test_registration_rejects_a_plain_http_redirect(self):
        response = self.client.post(
            "/oauth/register",
            data=json.dumps({"redirect_uris": ["http://evil.example.com/cb"]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_registration_allows_loopback(self):
        response = self.client.post(
            "/oauth/register",
            data=json.dumps({"redirect_uris": ["http://127.0.0.1:9000/cb"]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

    def register(self):
        response = self.client.post(
            "/oauth/register",
            data=json.dumps({"client_name": "Claude",
                             "redirect_uris": ["https://claude.ai/cb"]}),
            content_type="application/json",
        )
        return response.json()["client_id"]

    def test_consent_needs_the_admin_login(self):
        client_id = self.register()
        response = self.client.get("/oauth/authorize", {
            "client_id": client_id, "redirect_uri": "https://claude.ai/cb",
            "response_type": "code", "code_challenge": s256("v" * 50),
            "code_challenge_method": "S256",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_full_authorization_code_flow(self):
        client_id = self.register()
        verifier = "a" * 64
        self.client.force_login(self.user)

        params = {
            "client_id": client_id, "redirect_uri": "https://claude.ai/cb",
            "response_type": "code", "code_challenge": s256(verifier),
            "code_challenge_method": "S256", "state": "xyz", "scope": "write",
        }
        page = self.client.get("/oauth/authorize", params)
        self.assertContains(page, "Claude")

        approved = self.client.post("/oauth/authorize", {**params, "decision": "allow"})
        self.assertEqual(approved.status_code, 302)
        code = approved["Location"].split("code=")[1].split("&")[0]
        self.assertIn("state=xyz", approved["Location"])

        granted = self.client.post("/oauth/token", {
            "grant_type": "authorization_code", "code": code, "client_id": client_id,
            "redirect_uri": "https://claude.ai/cb", "code_verifier": verifier,
        }).json()
        self.assertEqual(granted["token_type"], "Bearer")

        listed = self.client.post(
            "/mcp", data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
            content_type="application/json",
            headers={"authorization": f"Bearer {granted['access_token']}"},
        )
        self.assertEqual(listed.status_code, 200)
        self.assertIn("create_project",
                      {t["name"] for t in listed.json()["result"]["tools"]})

        refreshed = self.client.post("/oauth/token", {
            "grant_type": "refresh_token", "refresh_token": granted["refresh_token"],
            "client_id": client_id,
        }).json()
        self.assertIn("access_token", refreshed)
        self.assertNotEqual(refreshed["access_token"], granted["access_token"])

        # The rotated pair is dead.
        reused = self.client.post("/oauth/token", {
            "grant_type": "refresh_token", "refresh_token": granted["refresh_token"],
            "client_id": client_id,
        })
        self.assertEqual(reused.status_code, 400)

    def test_wrong_verifier_is_refused(self):
        client_id = self.register()
        self.client.force_login(self.user)
        params = {
            "client_id": client_id, "redirect_uri": "https://claude.ai/cb",
            "response_type": "code", "code_challenge": s256("a" * 64),
            "code_challenge_method": "S256", "decision": "allow",
        }
        approved = self.client.post("/oauth/authorize", params)
        code = approved["Location"].split("code=")[1].split("&")[0]

        refused = self.client.post("/oauth/token", {
            "grant_type": "authorization_code", "code": code, "client_id": client_id,
            "redirect_uri": "https://claude.ai/cb", "code_verifier": "wrong",
        })
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(refused.json()["error"], "invalid_grant")

    def test_a_code_cannot_be_replayed(self):
        client_id = self.register()
        verifier = "b" * 64
        self.client.force_login(self.user)
        approved = self.client.post("/oauth/authorize", {
            "client_id": client_id, "redirect_uri": "https://claude.ai/cb",
            "response_type": "code", "code_challenge": s256(verifier),
            "code_challenge_method": "S256", "decision": "allow",
        })
        code = approved["Location"].split("code=")[1].split("&")[0]
        exchange = {
            "grant_type": "authorization_code", "code": code, "client_id": client_id,
            "redirect_uri": "https://claude.ai/cb", "code_verifier": verifier,
        }
        self.assertEqual(self.client.post("/oauth/token", exchange).status_code, 200)
        self.assertEqual(self.client.post("/oauth/token", exchange).status_code, 400)

    def test_denying_returns_access_denied(self):
        client_id = self.register()
        self.client.force_login(self.user)
        response = self.client.post("/oauth/authorize", {
            "client_id": client_id, "redirect_uri": "https://claude.ai/cb",
            "response_type": "code", "code_challenge": s256("c" * 64),
            "code_challenge_method": "S256", "decision": "deny",
        })
        self.assertIn("error=access_denied", response["Location"])

    def test_unregistered_redirect_uri_is_refused(self):
        client_id = self.register()
        self.client.force_login(self.user)
        response = self.client.get("/oauth/authorize", {
            "client_id": client_id, "redirect_uri": "https://attacker.example/cb",
            "response_type": "code", "code_challenge": s256("d" * 64),
            "code_challenge_method": "S256",
        })
        self.assertEqual(response.status_code, 400)

    def test_revocation_kills_the_token(self):
        client_id = self.register()
        verifier = "e" * 64
        self.client.force_login(self.user)
        approved = self.client.post("/oauth/authorize", {
            "client_id": client_id, "redirect_uri": "https://claude.ai/cb",
            "response_type": "code", "code_challenge": s256(verifier),
            "code_challenge_method": "S256", "decision": "allow",
        })
        code = approved["Location"].split("code=")[1].split("&")[0]
        granted = self.client.post("/oauth/token", {
            "grant_type": "authorization_code", "code": code, "client_id": client_id,
            "redirect_uri": "https://claude.ai/cb", "code_verifier": verifier,
        }).json()

        self.client.post("/oauth/revoke", {"token": granted["access_token"]})
        blocked = self.client.post(
            "/mcp", data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
            content_type="application/json",
            headers={"authorization": f"Bearer {granted['access_token']}"},
        )
        self.assertEqual(blocked.status_code, 401)
