"""Plain dict serializers — no DRF, since the API is read-only and shallow.

Each takes the resolved `lang` and reads content through Translatable.tr(),
which falls back field by field to the row's own language rather than to blank.
"""
from __future__ import annotations

from django.http import HttpRequest

from . import i18n
from .embeds import EmbedIndex, render_prose
from .models import Capability, Project, SiteProfile


def _abs(request: HttpRequest | None, url: str) -> str:
    """Absolute URL for a media file. S3 URLs already are; local /media/ paths
    need the host, which dev needs since Vite and Django are on different ports."""
    if not url:
        return ""
    if url.startswith(("http://", "https://", "//")):
        return url
    return request.build_absolute_uri(url) if request else url


def project_card(p: Project, request=None, lang=None) -> dict:
    """The shape the project list needs — no body, no assets."""
    return {
        "slug": p.slug,
        "title": p.tr("title", lang),
        "summary": p.tr("summary", lang),
        "domain": p.domain,
        "domain_label": i18n.term(f"domain.{p.domain}", lang),
        "year": p.year,
        "status": p.status,
        "status_label": i18n.term(f"status.{p.status}", lang),
        "featured": p.featured,
        "cover": _abs(request, p.cover.url if p.cover else ""),
        "cover_alt": p.tr("cover_alt", lang),
        "tags": [t.tr("name", lang) for t in p.tags.all()],
        "metric": {
            "label": p.tr("headline_metric_label", lang),
            "value": p.tr("headline_metric_value", lang),
        },
        "lang": lang or p.language,
    }


def project_detail(p: Project, request=None, lang=None) -> dict:
    """The full case study. `body_html` is the whole article: markdown, placed
    embeds, then the unplaced ones. The fact bar stays structured data because
    it renders above the title, outside the article column."""
    index = EmbedIndex(p, lang, request)
    body = index.render()

    data = project_card(p, request, lang)
    data.update({
        "standfirst": p.tr("standfirst", lang),
        "body_html": body.html,
        "toc": body.toc,
        "role": p.tr("role", lang),
        "client": p.tr("client", lang),
        "team": p.tr("team", lang),
        "duration": p.tr("duration", lang),
        "repo_url": p.repo_url,
        "live_url": p.live_url,
        "metrics": {
            "facts": index.facts(),
            "groups": index.groups_json(),
        },
        "assets": index.assets_json(),
        "updated_at": p.updated_at.isoformat(),
        "created_at": p.created_at.isoformat(),
        "available_languages": sorted({p.language, *p.translated_languages}),
    })
    return data


def capability(c: Capability, lang=None) -> dict:
    """One card in "What I run"."""
    return {
        "title": c.tr("title", lang),
        "body": c.tr("body", lang),
        "tools": c.tool_list(lang),
    }


def profile(pr: SiteProfile | None, request=None, lang=None, capabilities=()) -> dict:
    """The site chrome: identity, hero, about, capabilities, contact. Capability
    rows ride along here so the landing page still needs only one request."""
    if pr is None:
        return {}
    return {
        "name": pr.name,
        "role": pr.tr("role", lang),
        "location": pr.tr("location", lang),
        "availability": pr.tr("availability", lang),
        "hero_quote": pr.tr("hero_quote", lang),
        "hero_quote_attribution": pr.tr("hero_quote_attribution", lang),
        "intro": pr.tr("intro", lang),
        "bio_html": render_prose(pr.tr("bio_md", lang)),
        "capabilities_title": pr.tr("capabilities_title", lang),
        "capabilities_kicker": pr.tr("capabilities_kicker", lang),
        "capabilities": [capability(c, lang) for c in capabilities],
        "cta_headline": pr.tr("cta_headline", lang),
        "portrait": _abs(request, pr.portrait.url if pr.portrait else ""),
        "email": pr.email,
        "links": pr.links or {},
        "cv": _abs(request, pr.cv.url if pr.cv else ""),
        "lang": lang or pr.language,
        "available_languages": sorted({pr.language, *pr.translated_languages}),
    }
