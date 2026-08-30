"""The admin is the CMS: a project is one form, with its case study, numbers
and media inline, so publishing is a single save.

Two additions to a plain ModelAdmin: a Translations inline on every model that
holds prose, and a shortcode cheat-sheet on the project form so refs can be
copied into the body.
"""
from django import forms
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.db import models
from django.forms import Textarea
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from .models import (
    Asset, Capability, Metric, MetricGroup, MetricGroupItem, Project, SiteProfile, Tag,
    Translation,
)

MARKDOWN_WIDGET = {
    models.TextField: {"widget": Textarea(attrs={
        "rows": 28, "style": "font-family:ui-monospace,monospace;font-size:13px;line-height:1.6;width:95%",
        "spellcheck": "true",
    })},
}



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
            kwargs["widget"] = Textarea(attrs={"rows": 3, "style": "width:38rem"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class TranslatedAdminMixin:
    """Adds the translations inline and a 'which languages exist' column."""

    @admin.display(description="Languages")
    def languages(self, obj):
        others = obj.translated_languages
        return format_html(
            "<b>{}</b>{}", obj.language, (" + " + ", ".join(others)) if others else ""
        )



class MetricInline(admin.TabularInline):
    """The project's library of numbers. Tables are assembled from these."""

    model = Metric
    extra = 3
    fields = ("label", "baseline", "value", "delta", "note", "ref")
    readonly_fields = ("ref",)
    show_change_link = True


class MetricGroupItemInline(admin.TabularInline):
    model = MetricGroupItem
    extra = 4
    fields = ("order", "metric")
    autocomplete_fields = ("metric",)
    ordering = ("order", "id")


class MetricGroupInline(admin.TabularInline):
    """Tables live on the project; their contents are edited on their own page."""

    model = MetricGroup
    extra = 1
    fields = ("order", "layout", "title", "ref", "shortcode", "contents")
    readonly_fields = ("shortcode", "contents")
    show_change_link = True

    @admin.display(description="Paste into body")
    def shortcode(self, obj):
        if not obj.pk:
            return "—"
        return format_html("<code>{}</code>", obj.shortcode)

    @admin.display(description="Metrics")
    def contents(self, obj):
        if not obj.pk:
            return "Save, then add metrics on the table's own page."
        names = [m.label for m in obj.ordered_metrics()]
        return ", ".join(names) if names else "— none attached yet —"


@admin.register(Metric)
class MetricAdmin(TranslatedAdminMixin, admin.ModelAdmin):
    list_display = ("label", "value", "baseline", "delta", "project", "ref", "languages")
    list_filter = ("project", "language")
    search_fields = ("label", "value", "ref", "note")
    readonly_fields = ("ref",)
    inlines = [TranslationInline]
    fieldsets = (
        (None, {"fields": ("project", "language", "label", ("baseline", "value", "delta"), "note", "ref")}),
    )


@admin.register(MetricGroup)
class MetricGroupAdmin(TranslatedAdminMixin, admin.ModelAdmin):
    list_display = ("__str__", "project", "layout", "ref", "metric_count", "languages")
    list_filter = ("layout", "project")
    search_fields = ("title", "ref")
    inlines = [MetricGroupItemInline, TranslationInline]
    fieldsets = (
        (None, {
            "fields": ("project", "language", "layout", "title", "caption", ("ref", "order")),
            "description": "Reference this table from a project body with its shortcode, "
                           "e.g. <code>[[metrics:latency]]</code>. A table you never reference "
                           "still renders — fact bars under the title, everything else after "
                           "the body.",
        }),
    )

    @admin.display(description="Metrics")
    def metric_count(self, obj):
        return obj.items.count()



class AssetInline(admin.TabularInline):
    model = Asset
    extra = 2
    fields = ("order", "kind", "ratio", "image", "video", "poster", "caption", "alt", "shortcode")
    readonly_fields = ("shortcode",)
    show_change_link = True

    @admin.display(description="Paste into body")
    def shortcode(self, obj):
        if not obj.pk:
            return "—"
        return format_html("<code>{}</code>", obj.shortcode)


@admin.register(Asset)
class AssetAdmin(TranslatedAdminMixin, admin.ModelAdmin):
    list_display = ("__str__", "project", "kind", "ratio", "ref", "languages")
    list_filter = ("kind", "project")
    search_fields = ("caption", "alt", "ref")
    inlines = [TranslationInline]



@admin.register(Project)
class ProjectAdmin(TranslatedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "domain", "year", "status", "headline", "languages",
                    "featured", "published")
    list_filter = ("domain", "year", "status", "featured", "published", "language", "tags")
    list_editable = ("featured", "published")
    search_fields = ("title", "summary", "body_md", "tags__name")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)
    inlines = [MetricInline, MetricGroupInline, AssetInline, TranslationInline]
    formfield_overrides = MARKDOWN_WIDGET
    readonly_fields = ("embed_cheatsheet",)
    save_on_top = True

    fieldsets = (
        ("Listing", {
            "fields": ("title", "slug", "language", "summary", "domain", "year", "status",
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

        return format_html(
            '<table style="width:95%"><thead><tr>'
            '<th style="text-align:left">Shortcode</th><th style="text-align:left">Kind</th>'
            '<th style="text-align:left">What it is</th><th></th></tr></thead><tbody>{}</tbody></table>',
            format_html_join(
                "",
                '<tr><td><code style="user-select:all">{}</code></td><td>{}</td>'
                '<td>{}</td><td><a href="{}">edit</a></td></tr>',
                rows,
            ),
        )



@admin.register(SiteProfile)
class SiteProfileAdmin(TranslatedAdminMixin, admin.ModelAdmin):
    formfield_overrides = MARKDOWN_WIDGET
    inlines = [TranslationInline]
    fieldsets = (
        ("Identity", {"fields": ("name", "language", "role", "location", "availability", "intro")}),
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
            kwargs["widget"] = Textarea(attrs={"rows": 3, "style": "width:45rem"})
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
    inlines = [TranslationInline]
    formfield_overrides = {
        models.TextField: {"widget": Textarea(attrs={"rows": 4, "style": "width:45rem"})},
    }
    fieldsets = (
        (None, {
            "fields": ("language", "title", "body", "tools", ("order", "published")),
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
    inlines = [TranslationInline]

    @admin.display(description="Projects")
    def project_count(self, obj):
        return obj.projects.count()


admin.site.site_header = "Portfolio CMS"
admin.site.site_title = "Portfolio CMS"
admin.site.index_title = "Content"
