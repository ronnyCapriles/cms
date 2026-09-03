"""Shared lookups, validation and the source-form serializers.

portfolio.serializers renders markdown to HTML for the front end; these return
the source instead: body_md, refs and shortcodes.
"""
from __future__ import annotations

from django.db.models import Prefetch
from django.urls import reverse

from portfolio import i18n
from portfolio.embeds import EmbedIndex
from portfolio.models import (
    Asset, Capability, Domain, Metric, MetricGroup, Project, SiteProfile, Status, Tag,
)

from . import ToolError

MAX_UPLOAD_BYTES = 6 * 1024 * 1024

TRANSLATABLE_MODELS = {
    "project": Project,
    "site_profile": SiteProfile,
    "capability": Capability,
    "tag": Tag,
    "metric": Metric,
    "metric_group": MetricGroup,
    "asset": Asset,
}

DELETABLE_MODELS = {
    "project": Project,
    "capability": Capability,
    "tag": Tag,
    "metric": Metric,
    "metric_group": MetricGroup,
    "asset": Asset,
}


def check_language(lang):
    if lang and i18n.normalize(lang) is None:
        raise ToolError(
            f"Unknown language {lang!r}. Configured: {', '.join(i18n.available())}."
        )
    return lang


def get_project(slug: str) -> Project:
    project = (
        Project.objects.filter(slug=slug)
        .prefetch_related(
            "translations", "tags", "assets__translations", "metrics__translations",
            Prefetch(
                "metric_groups",
                queryset=MetricGroup.objects.prefetch_related(
                    "translations", "items__metric__translations"
                ),
            ),
        )
        .first()
    )
    if project is None:
        known = list(Project.objects.values_list("slug", flat=True)[:20])
        raise ToolError(f"No project with slug {slug!r}. Known slugs: {known}")
    return project


def get_profile() -> SiteProfile:
    profile = SiteProfile.objects.prefetch_related("translations").first()
    if profile is None:
        raise ToolError("No site profile exists yet; create one in the Django admin.")
    return profile


def get_asset(project: Project, ref: str) -> Asset:
    asset = project.assets.filter(ref=ref).first()
    if asset is None:
        refs = list(project.assets.values_list("ref", flat=True))
        raise ToolError(f"No asset {ref!r} on {project.slug}. Its assets: {refs}")
    return asset


def get_group(project: Project, ref: str) -> MetricGroup:
    group = project.metric_groups.filter(ref=ref).first()
    if group is None:
        refs = list(project.metric_groups.values_list("ref", flat=True))
        raise ToolError(f"No metric group {ref!r} on {project.slug}. Its groups: {refs}")
    return group


def get_metric(ref: str) -> Metric:
    metric = Metric.objects.filter(ref=ref).first()
    if metric is None:
        raise ToolError(f"No metric with ref {ref!r}.")
    return metric


def resolve_tags(names, create_missing=False) -> tuple[list[Tag], list[str]]:
    """Tags by slug or name. Returns the tags and the slugs newly created."""
    found, created = [], []
    for raw in names or []:
        needle = str(raw).strip()
        if not needle:
            continue
        tag = Tag.objects.filter(slug=needle).first() or Tag.objects.filter(
            name__iexact=needle
        ).first()
        if tag is None:
            if not create_missing:
                raise ToolError(
                    f"No tag matches {needle!r}. Call create_tag first, or pass "
                    f"create_missing: true."
                )
            tag = Tag.objects.create(name=needle)
            created.append(tag.slug)
        found.append(tag)
    return found, created


def apply_fields(obj, data: dict, allowed: set[str]) -> list[str]:
    """Assign the writable subset of `data` onto `obj`. Returns what changed."""
    unknown = set(data) - allowed
    if unknown:
        raise ToolError(
            f"Not writable here: {sorted(unknown)}. Writable: {sorted(allowed)}"
        )
    changed = []
    for name, value in data.items():
        if getattr(obj, name) != value:
            setattr(obj, name, value)
            changed.append(name)
    return changed


def admin_url(obj) -> str:
    meta = obj._meta
    return reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[obj.pk])


def metric_source(metric: Metric) -> dict:
    return {
        "ref": metric.ref,
        "label": metric.label,
        "value": metric.value,
        "baseline": metric.baseline,
        "delta": metric.delta,
        "note": metric.note,
        "language": metric.language,
    }


def group_source(group: MetricGroup, placed: set[str]) -> dict:
    return {
        "ref": group.ref,
        "shortcode": group.shortcode,
        "layout": group.layout,
        "title": group.title,
        "caption": group.caption,
        "order": group.order,
        "placed_in_body": group.shortcode in placed,
        "metric_refs": [m.ref for m in group.ordered_metrics()],
    }


def asset_source(asset: Asset, placed: set[str], absolute=None) -> dict:
    url = asset.url
    return {
        "ref": asset.ref,
        "shortcode": asset.shortcode,
        "kind": asset.kind,
        "ratio": asset.ratio,
        "caption": asset.caption,
        "alt": asset.alt,
        "order": asset.order,
        "has_file": bool(asset.file),
        "placed_in_body": asset.shortcode in placed,
        "url": absolute(url) if absolute else url,
    }


def project_card(project: Project) -> dict:
    return {
        "slug": project.slug,
        "title": project.title,
        "summary": project.summary,
        "domain": project.domain,
        "year": project.year,
        "status": project.status,
        "published": project.published,
        "featured": project.featured,
        "order": project.order,
        "language": project.language,
        "tags": [t.slug for t in project.tags.all()],
        "translated_languages": project.translated_languages,
        "updated_at": project.updated_at,
    }


def project_source(project: Project, request=None) -> dict:
    """The case study in source form."""
    body = project.body_md or ""
    placed = {code for code in _shortcodes(project) if code in body}

    def absolute(url):
        if not url or not request or url.startswith(("http://", "https://", "//")):
            return url
        return request.build_absolute_uri(url)

    data = project_card(project)
    data.update({
        "standfirst": project.standfirst,
        "body_md": body,
        "role": project.role,
        "client": project.client,
        "team": project.team,
        "duration": project.duration,
        "cover": {"url": absolute(project.cover.url if project.cover else ""),
                  "alt": project.cover_alt},
        "headline_metric": {"label": project.headline_metric_label,
                            "value": project.headline_metric_value},
        "repo_url": project.repo_url,
        "live_url": project.live_url,
        "metrics_library": [metric_source(m) for m in project.metrics.all()],
        "metric_groups": [group_source(g, placed) for g in project.metric_groups.all()],
        "assets": [asset_source(a, placed, absolute) for a in project.assets.all()],
        "translations": translations_of(project),
        "translation_coverage": project.coverage(),
        "urls": {"public": project.get_absolute_url(), "admin": admin_url(project)},
    })
    return data


def _shortcodes(project: Project):
    for group in project.metric_groups.all():
        yield group.shortcode
    for asset in project.assets.all():
        yield asset.shortcode


def translations_of(obj) -> dict:
    out: dict[str, dict[str, str]] = {}
    for (lang, field), value in obj._translation_map().items():
        out.setdefault(lang, {})[field] = value
    return out


def profile_source(profile: SiteProfile, request=None) -> dict:
    def absolute(url):
        if not url or not request or url.startswith(("http://", "https://", "//")):
            return url
        return request.build_absolute_uri(url)

    return {
        "name": profile.name,
        "language": profile.language,
        "role": profile.role,
        "location": profile.location,
        "availability": profile.availability,
        "hero_quote": profile.hero_quote,
        "hero_quote_attribution": profile.hero_quote_attribution,
        "intro": profile.intro,
        "bio_md": profile.bio_md,
        "capabilities_title": profile.capabilities_title,
        "capabilities_kicker": profile.capabilities_kicker,
        "cta_headline": profile.cta_headline,
        "email": profile.email,
        "links": profile.links or {},
        "portrait": absolute(profile.portrait.url if profile.portrait else ""),
        "cv": absolute(profile.cv.url if profile.cv else ""),
        "translations": translations_of(profile),
        "translation_coverage": profile.coverage(),
        "urls": {"admin": admin_url(profile)},
    }


def capability_source(capability: Capability) -> dict:
    return {
        "id": capability.pk,
        "title": capability.title,
        "body": capability.body,
        "tools": capability.tool_list(),
        "order": capability.order,
        "published": capability.published,
        "language": capability.language,
        "translation_coverage": capability.coverage(),
    }


def render_index(project: Project, lang=None, request=None) -> EmbedIndex:
    return EmbedIndex(project, lang, request)


CHOICES = {
    "domain": [c[0] for c in Domain.choices],
    "status": [c[0] for c in Status.choices],
    "asset_kind": [c[0] for c in Asset.KIND],
    "asset_ratio": [c[0] for c in Asset.RATIO],
    "metric_group_layout": [c[0] for c in MetricGroup.LAYOUT],
    "tag_kind": ["tech", "concept", "cloud"],
}

# `published` is absent on purpose: publish_project is the only way it moves.
PROJECT_WRITABLE = {
    "title", "slug", "language", "summary", "standfirst", "body_md", "domain",
    "year", "status", "role", "client", "team", "duration", "cover_alt",
    "headline_metric_label", "headline_metric_value", "repo_url", "live_url",
    "featured", "order",
}

PROFILE_WRITABLE = {
    "name", "language", "role", "location", "availability", "hero_quote",
    "hero_quote_attribution", "intro", "bio_md", "capabilities_title",
    "capabilities_kicker", "cta_headline", "email", "links",
}

CAPABILITY_WRITABLE = {"title", "body", "tools", "order", "published", "language"}

TAG_WRITABLE = {"name", "slug", "kind", "language"}

METRIC_WRITABLE = {"label", "value", "baseline", "delta", "note", "ref", "language"}

GROUP_WRITABLE = {"title", "caption", "layout", "ref", "order", "language"}

ASSET_WRITABLE = {"kind", "ratio", "caption", "alt", "ref", "order", "language"}
