"""The admin is the CMS: a project is one form, with its case study, numbers
and media inline, so publishing is a single save.

Styling lives in static/cms_admin/admin.css, behaviour in admin.js.
"""
from django import forms
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.core.exceptions import PermissionDenied
from django.db import models
from django.forms import Textarea
from django.http import Http404, JsonResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html, format_html_join
from django.views.decorators.http import require_POST

from . import i18n
from .assets import asset_url
from .embeds import EmbedIndex, render_prose
from .markdown_render import render as render_markdown
from .models import (
    Asset, Capability, Metric, MetricGroup, MetricGroupItem, Project, SiteProfile, Tag,
    Translation,
)

MARKDOWN_WIDGET = {
    models.TextField: {"widget": Textarea(attrs={
        "rows": 28, "class": "cms-markdown", "spellcheck": "true",
    })},
}


def copy_button(text: str, label: str | None = None):
    return format_html(
        '<button type="button" class="cms-copy" data-cms-copy="{}" '
        'title="Copy to clipboard">{}</button>',
        text, label or text,
    )



class MarkdownPreviewMixin:
    """Live preview beside a markdown field, rendered by the same call the API
    makes. List the fields in MARKDOWN_PREVIEW_FIELDS."""

    MARKDOWN_PREVIEW_FIELDS: tuple[str, ...] = ()

    def _preview_url_name(self) -> str:
        meta = self.model._meta
        return f"{meta.app_label}_{meta.model_name}_markdown_preview"

    def get_urls(self):
        # Must come first, or ModelAdmin's <path:object_id>/ catches it.
        return [
            path(
                "markdown-preview/",
                self.admin_site.admin_view(self.markdown_preview_view),
                name=self._preview_url_name(),
            ),
        ] + super().get_urls()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        url = reverse(f"admin:{self._preview_url_name()}")
        for name in self.MARKDOWN_PREVIEW_FIELDS:
            field = form.base_fields.get(name)
            if field is None:
                continue
            field.widget.attrs.update({
                "data-cms-preview-url": url,
                "data-cms-preview-pk": str(obj.pk) if obj and obj.pk else "",
            })
        return form

    def markdown_preview_index(self, request, obj, lang):
        """Override to resolve `[[kind:ref]]` against `obj`; None renders plain prose."""
        return None

    def render_markdown_preview(self, request, text, obj, lang) -> str:
        index = self.markdown_preview_index(request, obj, lang) if obj else None
        if index is None:
            return render_prose(text)
        # trailing_html() reads what render() placed, so it has to run after.
        body = render_markdown(text, index.resolve)
        return body.html + index.trailing_html()

    @method_decorator(require_POST)
    def markdown_preview_view(self, request):
        """POST {text, lang, pk} -> {html}."""
        if not (self.has_change_permission(request) or self.has_add_permission(request)):
            raise PermissionDenied

        obj, pk = None, request.POST.get("pk")
        if pk:
            obj = self.get_queryset(request).filter(pk=pk).first()
            if obj is None:
                raise Http404("No such object.")

        html = self.render_markdown_preview(
            request,
            request.POST.get("text", ""),
            obj,
            i18n.normalize(request.POST.get("lang")),
        )
        return JsonResponse({"html": html})



class TranslationInline(GenericTabularInline):
    """Attach to any Translatable model; the field list follows the parent."""

    model = Translation
    ct_field = "content_type"
    ct_fk_field = "object_id"
    extra = 0
    fields = ("lang", "field", "value")
    verbose_name = "translation"
    verbose_name_plural = "translations"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "field":
            names = getattr(self.parent_model, "TRANSLATABLE_FIELDS", ())
            return forms.ChoiceField(
                choices=[(n, n.replace("_", " ")) for n in names],
                label="Field",
                help_text="" if names else "This model has no translatable fields.",
            )
        if db_field.name == "value":
            kwargs["widget"] = Textarea(attrs={"rows": 3, "class": "cms-translation-value"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class TranslatedAdminMixin:
    """The translations inline, plus how much of the original is translated.
    A field only counts as missing when the original has something in it."""

    @property
    def media(self):
        # Versioned; see assets.py.
        return super().media + forms.Media(js=[asset_url("cms_admin/admin.js")])

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("translations")

    @staticmethod
    def _coverage(obj):
        """[(lang, done, total, [missing field names])] for the other languages."""
        return [(c["lang"], c["done"], c["total"], c["missing"]) for c in obj.coverage()]

    @admin.display(description="Languages")
    def languages(self, obj):
        if not obj.pk:
            return "—"
        badges = [("source", obj.language, "original")]
        for lang, done, total, _missing in self._coverage(obj):
            if total == 0:
                state, count = "none", "n/a"
            elif done == total:
                state, count = "full", f"{done}/{total}"
            elif done == 0:
                state, count = "none", f"0/{total}"
            else:
                state, count = "part", f"{done}/{total}"
            badges.append((state, lang, count))
        return format_html(
            '<span class="cms-cov">{}</span>',
            format_html_join(
                "",
                '<span class="cms-cov__lang cms-cov__lang--{}">{} {}</span>',
                badges,
            ),
        )

    @admin.display(description="Translation coverage")
    def translation_coverage(self, obj):
        """The same count as the column, but naming the fields still missing."""
        if not obj or not obj.pk:
            return "Save first; coverage is counted against what the original fills."

        rows = []
        for lang, done, total, missing in self._coverage(obj):
            if total == 0:
                body = format_html('<span class="cms-empty">nothing to translate yet</span>')
            elif not missing:
                body = format_html("complete, {} of {} fields", done, total)
            else:
                body = format_html(
                    '{} of {}, missing <span class="cms-missing">{}</span>',
                    done, total, ", ".join(m.replace("_", " ") for m in missing),
                )
            rows.append((lang, body))

        if not rows:
            return "Only one content language is configured."
        return format_html(
            '<dl class="cms-cov-detail">{}</dl>',
            format_html_join("", "<dt>{}</dt><dd>{}</dd>", rows),
        )


class OrderableInlineMixin:
    """Rows can be dragged; admin.js writes the `order` inputs on drop."""

    classes = ("cms-sortable",)



class MetricInline(admin.TabularInline):
    """The project's library of numbers. Tables are assembled from these."""

    model = Metric
    extra = 3
    fields = ("label", "baseline", "value", "delta", "note", "ref")
    readonly_fields = ("ref",)
    show_change_link = True


class MetricGroupItemInline(OrderableInlineMixin, admin.TabularInline):
    model = MetricGroupItem
    extra = 4
    fields = ("order", "metric")
    autocomplete_fields = ("metric",)
    ordering = ("order", "id")


class MetricGroupInline(OrderableInlineMixin, admin.TabularInline):
    """Tables live on the project; their contents are edited on their own page."""

    model = MetricGroup
    extra = 1
    fields = ("order", "layout", "title", "ref", "shortcode", "contents")
    readonly_fields = ("shortcode", "contents")
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("items__metric")

    @admin.display(description="Paste into body")
    def shortcode(self, obj):
        if not obj.pk:
            return "—"
        return copy_button(obj.shortcode)

    @admin.display(description="Metrics")
    def contents(self, obj):
        if not obj.pk:
            return "Save, then add metrics on the table's own page."
        names = [m.label for m in obj.ordered_metrics()]
        if names:
            return ", ".join(names)
        return format_html('<span class="cms-empty">none attached yet</span>')


@admin.register(Metric)
class MetricAdmin(TranslatedAdminMixin, admin.ModelAdmin):
    list_display = ("label", "value", "baseline", "delta", "project", "ref", "languages")
    list_filter = ("project", "language")
    search_fields = ("label", "value", "ref", "note")
    readonly_fields = ("ref", "translation_coverage")
    list_select_related = ("project",)
    inlines = [TranslationInline]
    fieldsets = (
        (None, {"fields": ("project", "language", "label", ("baseline", "value", "delta"),
                           "note", "ref", "translation_coverage")}),
    )


@admin.register(MetricGroup)
class MetricGroupAdmin(TranslatedAdminMixin, admin.ModelAdmin):
    list_display = ("__str__", "project", "layout", "ref", "metric_count", "languages")
    list_filter = ("layout", "project")
    search_fields = ("title", "ref")
    list_select_related = ("project",)
    readonly_fields = ("translation_coverage",)
    inlines = [MetricGroupItemInline, TranslationInline]
    fieldsets = (
        (None, {
            "fields": ("project", "language", "layout", "title", "caption", ("ref", "order"),
                       "translation_coverage"),
            "description": "Reference this table from a project body with its shortcode, "
                           "e.g. <code>[[metrics:latency]]</code>. A table you never reference "
                           "still renders — fact bars under the title, everything else after "
                           "the body.",
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("items")

    @admin.display(description="Metrics")
    def metric_count(self, obj):
        return len(obj.items.all())



class AssetInline(OrderableInlineMixin, admin.TabularInline):
    model = Asset
    extra = 2
    fields = ("order", "preview", "kind", "ratio", "image", "video", "poster",
              "caption", "alt", "shortcode")
    readonly_fields = ("preview", "shortcode")
    show_change_link = True

    @admin.display(description="Paste into body")
    def shortcode(self, obj):
        if not obj.pk:
            return "—"
        return copy_button(obj.shortcode)

    @admin.display(description="Preview")
    def preview(self, obj):
        return asset_thumbnail(obj)


def asset_thumbnail(obj):
    if obj is None or not obj.pk:
        return format_html('<span class="cms-thumb cms-thumb--none">new</span>')
    src = obj.poster_url if obj.kind == "video" else obj.url
    if not src:
        return format_html(
            '<span class="cms-thumb cms-thumb--none">{}</span>',
            "no poster" if obj.kind == "video" else "no file",
        )
    return format_html(
        '<img class="cms-thumb" src="{}" alt="" loading="lazy" decoding="async">', src
    )


@admin.register(Asset)
class AssetAdmin(TranslatedAdminMixin, admin.ModelAdmin):
    list_display = ("thumbnail", "__str__", "project", "kind", "ratio", "ref", "languages")
    list_display_links = ("thumbnail", "__str__")
    list_filter = ("kind", "project")
    search_fields = ("caption", "alt", "ref")
    list_select_related = ("project",)
    readonly_fields = ("thumbnail", "translation_coverage")
    inlines = [TranslationInline]
    fieldsets = (
        (None, {
            "fields": ("project", "language", ("kind", "ratio"), "thumbnail",
                       "image", "video", "poster", "caption", "alt",
                       ("ref", "order"), "translation_coverage"),
        }),
    )

    @admin.display(description="Preview")
    def thumbnail(self, obj):
        return asset_thumbnail(obj)



@admin.register(Project)
class ProjectAdmin(MarkdownPreviewMixin, TranslatedAdminMixin, admin.ModelAdmin):
    MARKDOWN_PREVIEW_FIELDS = ("body_md",)

    list_display = ("title", "domain", "year", "status", "headline", "languages",
                    "featured", "published")
    list_filter = ("domain", "year", "status", "featured", "published", "language", "tags")
    list_editable = ("featured", "published")
    search_fields = ("title", "summary", "body_md", "tags__name")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)
    inlines = [MetricInline, MetricGroupInline, AssetInline, TranslationInline]
    formfield_overrides = MARKDOWN_WIDGET
    readonly_fields = ("embed_cheatsheet", "translation_coverage")
    save_on_top = True

    fieldsets = (
        ("Listing", {
            "fields": ("title", "slug", "language", "translation_coverage", "summary",
                       "domain", "year", "status",
                       ("headline_metric_label", "headline_metric_value"),
                       "tags", ("featured", "published", "order")),
        }),
        ("Detail page", {
            "fields": ("standfirst", "embed_cheatsheet", "body_md"),
            "description": "The body is markdown. Its headings become the on-page contents list.",
        }),
        ("Credits", {
            "fields": (("role", "client"), ("team", "duration")),
            "classes": ("collapse",),
        }),
        ("Media & links", {
            "fields": ("cover", "cover_alt", ("repo_url", "live_url")),
        }),
    )

    def markdown_preview_index(self, request, obj, lang):
        return EmbedIndex(obj, lang, request)

    @admin.display(description="Headline")
    def headline(self, obj):
        if not obj.headline_metric_value:
            return "—"
        return format_html("<b>{}</b> {}", obj.headline_metric_value, obj.headline_metric_label)

    @admin.display(description="Place in the body")
    def embed_cheatsheet(self, obj):
        """Every shortcode this project can use, ready to copy. A shortcode moves
        a block into the body; anything unplaced is still appended after it."""
        if not obj.pk:
            return "Save the project first; media and tables get their refs then."

        body = obj.body_md or ""
        rows = [
            (g.shortcode, g.get_layout_display(), g.title or f"{g.items.count()} metrics",
             reverse("admin:portfolio_metricgroup_change", args=[g.pk]))
            for g in obj.metric_groups.all()
        ] + [
            (a.shortcode, a.get_kind_display(), a.caption or a.alt or "—",
             reverse("admin:portfolio_asset_change", args=[a.pk]))
            for a in obj.assets.all()
        ]
        if not rows:
            return "No media or metric tables yet — add them below and save."

        cells = [
            (copy_button(shortcode), kind,
             format_html('<span class="cms-kind">{}</span>',
                         "placed" if shortcode in body else "appended"),
             what, url)
            for shortcode, kind, what, url in rows
        ]
        return format_html(
            '<table class="cms-cheatsheet"><thead><tr>'
            "<th>Shortcode</th><th>Kind</th><th>In body</th><th>What it is</th><th></th>"
            "</tr></thead><tbody>{}</tbody></table>",
            format_html_join(
                "",
                '<tr><td>{}</td><td class="cms-what">{}</td><td>{}</td>'
                '<td class="cms-what">{}</td><td><a href="{}">edit</a></td></tr>',
                cells,
            ),
        )



@admin.register(SiteProfile)
class SiteProfileAdmin(MarkdownPreviewMixin, TranslatedAdminMixin, admin.ModelAdmin):
    MARKDOWN_PREVIEW_FIELDS = ("bio_md",)

    formfield_overrides = MARKDOWN_WIDGET
    readonly_fields = ("translation_coverage",)
    inlines = [TranslationInline]
    fieldsets = (
        ("Identity", {"fields": ("name", "language", "translation_coverage", "role",
                                 "location", "availability", "intro")}),
        ("Hero quote", {
            "fields": ("hero_quote", "hero_quote_attribution"),
            "description": "The single line in the hero. Keep it under ~20 words.",
        }),
        ("About", {"fields": ("bio_md", "portrait")}),
        ("Capabilities", {
            "fields": ("capabilities_title", "capabilities_kicker"),
            "description": "Just the heading over the section. The cards themselves are "
                           '<b>Capabilities</b>, edited as their own list.',
        }),
        ("Contact", {
            "fields": ("cta_headline", "email", "links", "cv"),
            "description": "The closing line takes two bits of markup and no more: a line "
                           "break is a line break, and <code>*asterisks*</code> outline a "
                           "word — e.g. <code>Let&#x27;s move\nsome *data*</code>.",
        }),
    )

    # These want a small box, not the 28-row markdown widget.
    SHORT_PROSE = {"hero_quote", "cta_headline"}

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in self.SHORT_PROSE:
            kwargs["widget"] = Textarea(attrs={"rows": 3, "class": "cms-prose"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def has_add_permission(self, request):
        return not SiteProfile.objects.exists()  # singleton

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Capability)
class CapabilityAdmin(TranslatedAdminMixin, admin.ModelAdmin):
    """The "What I run" cards, in the order they appear."""

    list_display = ("title", "chips", "order", "languages", "published")
    list_editable = ("order", "published")
    list_filter = ("published", "language")
    search_fields = ("title", "body", "tools")
    readonly_fields = ("translation_coverage",)
    inlines = [TranslationInline]
    formfield_overrides = {
        models.TextField: {"widget": Textarea(attrs={"rows": 4, "class": "cms-prose"})},
    }
    fieldsets = (
        (None, {
            "fields": ("language", "translation_coverage", "title", "body", "tools",
                       ("order", "published")),
            "description": "One card in the capabilities section. Cards are numbered "
                           "EDGE 01, 02, … in this order, so the numbering follows the "
                           "list rather than being typed in.",
        }),
    )

    @admin.display(description="Tools")
    def chips(self, obj):
        return ", ".join(obj.tool_list()) or "—"


@admin.register(Tag)
class TagAdmin(TranslatedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "kind", "project_count", "languages")
    list_filter = ("kind",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("translation_coverage",)
    inlines = [TranslationInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "kind", "language", "translation_coverage")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("projects")

    @admin.display(description="Projects")
    def project_count(self, obj):
        return len(obj.projects.all())


admin.site.site_header = "Portfolio CMS"
admin.site.site_title = "Portfolio CMS"
admin.site.index_title = "Content"
