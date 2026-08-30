"""Read-only JSON API, plus the template that boots the React app.

Every endpoint answers in one language, resolved per request (see i18n.resolve)
and reported back both in the payload and as a Content-Language header.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.db.models import Count, Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import render as django_render
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET

from . import i18n, serializers
from .models import Capability, Domain, MetricGroup, Project, SiteProfile, Status, Tag


def _localized(response, lang: str):
    """Stamp the language on a response and declare what it varies on — the same
    URL answers differently per language, and caches in front need to know."""
    response["Content-Language"] = lang
    patch_vary_headers(response, ["Accept-Language", "X-Language"])
    return response


def _json(request, payload: dict, lang: str) -> JsonResponse:
    return _localized(JsonResponse(payload), lang)


@require_GET
def profile(request):
    lang = i18n.resolve(request)
    site = SiteProfile.objects.prefetch_related("translations").first()
    capabilities = (
        Capability.objects.filter(published=True).prefetch_related("translations")
    )
    return _json(request, serializers.profile(site, request, lang, capabilities), lang)


@require_GET
def project_list(request):
    """Filterable list. Every filter is optional and they compose.

    ?domain=streaming&tag=kafka&year=2026&q=iceberg&featured=1&lang=es
    """
    lang = i18n.resolve(request)
    qs = (
        Project.objects.filter(published=True)
        .prefetch_related("translations", "tags__translations")
    )

    domain = request.GET.get("domain")
    if domain and domain != "all":
        qs = qs.filter(domain=domain)

    tag = request.GET.get("tag")
    if tag:
        qs = qs.filter(tags__slug=tag)

    year = request.GET.get("year")
    if year and year.isdigit():
        qs = qs.filter(year=int(year))

    if request.GET.get("featured") == "1":
        qs = qs.filter(featured=True)

    q = (request.GET.get("q") or "").strip()
    if q:
        # Search translations too, so a Spanish query finds a Spanish title.
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(summary__icontains=q)
            | Q(tags__name__icontains=q)
            | Q(translations__value__icontains=q)
            | Q(tags__translations__value__icontains=q)
        )

    qs = qs.distinct()
    return _json(request, {
        "count": qs.count(),
        "lang": lang,
        "results": [serializers.project_card(p, request, lang) for p in qs],
    }, lang)


@require_GET
def project_detail(request, slug):
    lang = i18n.resolve(request)
    groups = MetricGroup.objects.prefetch_related(
        "translations", "items__metric__translations"
    )
    try:
        p = (
            Project.objects.filter(published=True)
            .prefetch_related(
                "translations",
                "tags__translations",
                "assets__translations",
                Prefetch("metric_groups", queryset=groups),
            )
            .get(slug=slug)
        )
    except Project.DoesNotExist as exc:
        raise Http404("No such project") from exc

    siblings = list(
        Project.objects.filter(published=True).prefetch_related("translations")
    )
    idx = next((i for i, s in enumerate(siblings) if s.slug == slug), None)
    prev_ = siblings[idx - 1] if idx not in (None, 0) else None
    next_ = siblings[idx + 1] if idx is not None and idx + 1 < len(siblings) else None

    def link(project):
        return {"slug": project.slug, "title": project.tr("title", lang)} if project else None

    data = serializers.project_detail(p, request, lang)
    data["prev"] = link(prev_)
    data["next"] = link(next_)
    return _json(request, data, lang)


@require_GET
def filters(request):
    """Facets for the filter UI, with counts so empty chips can be hidden."""
    lang = i18n.resolve(request)
    published = Project.objects.filter(published=True)
    domains = {row["domain"]: row["n"] for row in published.values("domain").annotate(n=Count("id"))}
    tags = (
        Tag.objects.prefetch_related("translations")
        .annotate(n=Count("projects", filter=Q(projects__published=True)))
        .filter(n__gt=0)
    )
    return _json(request, {
        "lang": lang,
        "domains": [
            {"value": value, "label": i18n.term(f"domain.{value}", lang),
             "count": domains.get(value, 0)}
            for value, _ in Domain.choices
        ],
        "statuses": [
            {"value": value, "label": i18n.term(f"status.{value}", lang)}
            for value, _ in Status.choices
        ],
        "tags": [
            {"slug": t.slug, "name": t.tr("name", lang), "count": t.n} for t in tags
        ],
        "years": sorted(published.values_list("year", flat=True).distinct(), reverse=True),
    }, lang)


@require_GET
def languages(request):
    """What the site can be read in, and what this request resolved to."""
    lang = i18n.resolve(request)
    return _json(request, {
        "lang": lang,
        "default": i18n.default(),
        "available": [
            {"code": code, "label": dict(i18n.Language.choices).get(code, code)}
            for code in i18n.available()
        ],
    }, lang)


_MANIFEST = Path(settings.BASE_DIR) / "portfolio" / "static" / "app" / ".vite" / "manifest.json"


def _vite_entry() -> dict:
    """The hashed entry files from Vite's manifest, so no filename is hard-coded
    here. Returns built=False when there is no build, i.e. use the dev server."""
    if _MANIFEST.exists():
        manifest = json.loads(_MANIFEST.read_text())
        entry = manifest.get("src/main.jsx") or next(iter(manifest.values()))
        return {
            "built": True,
            "js": f"app/{entry['file']}",
            "css": [f"app/{c}" for c in entry.get("css", [])],
        }
    return {"built": False, "js": "", "css": []}


def spa(request):
    lang = i18n.resolve(request)
    return _localized(
        django_render(request, "portfolio/index.html", {
            "vite": _vite_entry(),
            "theme": settings.PORTFOLIO_THEME,
            "lang": lang,
            "languages": i18n.available(),
            "debug": settings.DEBUG,
        }),
        lang,
    )
