"""Which language a request gets, and the words the server renders itself.

Copy is split three ways: UI chrome ships in the React bundle, content is
translated per row in the CMS (models.Translation), and the few words the
server itself writes into HTML live in TERMS below.

Language is picked first-match-wins: ?lang=, X-Language, Accept-Language,
then CONTENT_LANGUAGE_DEFAULT.
"""
from __future__ import annotations

import re

from django.conf import settings
from django.db import models


class Language(models.TextChoices):
    EN = "en", "English"
    ES = "es", "Español"


def available() -> list[str]:
    return list(getattr(settings, "CONTENT_LANGUAGES", ["en"]))


def default() -> str:
    return getattr(settings, "CONTENT_LANGUAGE_DEFAULT", "en")


def normalize(tag: str | None) -> str | None:
    """`es-419`, `ES_es`, `es` all mean `es` — if `es` is one of ours."""
    if not tag:
        return None
    base = re.split(r"[-_]", tag.strip().lower())[0]
    return base if base in available() else None


_QUALITY = re.compile(r"^\s*([^;]+?)\s*(?:;\s*q\s*=\s*([0-9.]+))?\s*$")


def parse_accept_language(header: str | None) -> list[str]:
    """Accept-Language, highest quality first, filtered to languages we serve."""
    if not header:
        return []
    scored: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")):
        match = _QUALITY.match(part)
        if not match:
            continue
        tag, quality = match.group(1), match.group(2)
        if tag == "*":
            continue
        try:
            weight = float(quality) if quality is not None else 1.0
        except ValueError:
            weight = 1.0
        lang = normalize(tag)
        # `index` breaks ties in the header's own order.
        if lang and weight > 0:
            scored.append((-weight, index, lang))
    seen, ordered = set(), []
    for _, _, lang in sorted(scored):
        if lang not in seen:
            seen.add(lang)
            ordered.append(lang)
    return ordered


def resolve(request) -> str:
    """The language this request should be answered in."""
    if request is None:
        return default()
    explicit = (
        normalize(request.GET.get("lang"))
        or normalize(request.headers.get("X-Language"))
    )
    if explicit:
        return explicit
    from_browser = parse_accept_language(request.headers.get("Accept-Language"))
    return from_browser[0] if from_browser else default()


# Words the server renders into HTML or into choice labels.
TERMS: dict[str, dict[str, str]] = {
    # Project.domain
    "domain.streaming": {"en": "Streaming", "es": "Streaming"},
    "domain.batch": {"en": "Batch", "es": "Batch"},
    "domain.ai_ml": {"en": "AI / ML", "es": "IA / ML"},
    "domain.infra": {"en": "Infrastructure", "es": "Infraestructura"},
    # Project.status
    "status.live": {"en": "In production", "es": "En producción"},
    "status.archived": {"en": "Archived", "es": "Archivado"},
    "status.wip": {"en": "In progress", "es": "En curso"},
    # Asset.kind, used in the empty-slot placeholder
    "kind.image": {"en": "Image", "es": "Imagen"},
    "kind.video": {"en": "Video", "es": "Video"},
    "kind.diagram": {"en": "Diagram", "es": "Diagrama"},
    # Metric tables rendered server-side
    "metrics.impact": {"en": "Measured impact", "es": "Impacto medido"},
    "metrics.metric": {"en": "Metric", "es": "Métrica"},
    "metrics.before": {"en": "Before", "es": "Antes"},
    "metrics.after": {"en": "After", "es": "Después"},
    "metrics.value": {"en": "Value", "es": "Valor"},
    "metrics.change": {"en": "Change", "es": "Cambio"},
    "metrics.note": {"en": "Note", "es": "Nota"},
}


def term(key: str, lang: str | None = None) -> str:
    """A server-rendered word, falling back through default language to the key."""
    entry = TERMS.get(key)
    if not entry:
        return key
    return entry.get(lang or default()) or entry.get(default()) or entry.get("en") or key
