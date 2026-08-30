"""Placing assets and metric tables inside a case study.

A body names them by ref:

    [[asset:9f2a1c07]]      any kind of asset
    [[image:9f2a1c07]]      the same, but only if it really is an image
    [[metrics:latency]]     a metric table, in its group's layout

EmbedIndex does that lookup for one project in one language, and appends
whatever the body never named. Placing something is a move, not a copy.
"""
from __future__ import annotations

from django.utils.html import escape

from . import i18n
from .markdown_render import Rendered, render


def render_prose(text: str) -> str:
    """Markdown with no embeds — the bio, and anything else short."""
    return render(text).html



def asset_html(asset, lang: str | None = None, absolute=None) -> str:
    """A `<figure>` for an image, a video, or the placeholder slot for neither."""
    url = asset.url
    poster = asset.poster_url
    if absolute:
        url, poster = absolute(url), absolute(poster)

    caption = asset.tr("caption", lang)
    alt = asset.tr("alt", lang) or caption

    if asset.kind == "video" and url:
        poster_attr = f' poster="{escape(poster)}"' if poster else ""
        media = (f'<video controls preload="metadata"{poster_attr} '
                 f'src="{escape(url)}"></video>')
    elif url:
        media = (f'<img src="{escape(url)}" alt="{escape(alt)}" '
                 f'loading="lazy" decoding="async" />')
    else:
        # Nothing uploaded yet: show the slot's shape so the layout can be
        # judged before the media exists.
        video_class = " slot--video" if asset.kind == "video" else ""
        label = i18n.term(f"kind.{asset.kind}", lang).upper()
        media = (f'<div class="slot slot--{escape(asset.ratio)}{video_class}">'
                 f'[ {escape(label)} · {escape(asset.ratio.replace("x", ":"))} ]</div>')

    figcaption = f"<figcaption>{escape(caption)}</figcaption>" if caption else ""
    return (f'<figure class="embed embed--{escape(asset.kind)}" '
            f'id="asset-{escape(asset.ref)}">{media}{figcaption}</figure>')



def _cells(metric, lang):
    return {
        "label": metric.tr("label", lang),
        "value": metric.tr("value", lang),
        "baseline": metric.tr("baseline", lang),
        "delta": metric.tr("delta", lang),
        "note": metric.tr("note", lang),
    }


def group_html(group, lang: str | None = None) -> str:
    """Render a metric group in its own layout. Empty groups render nothing."""
    rows = [_cells(m, lang) for m in group.ordered_metrics()]
    if not rows:
        return ""

    title = group.tr("title", lang)
    caption = group.tr("caption", lang)
    anchor = f'id="metrics-{escape(group.ref)}"'

    if group.layout == "facts":
        facts = "".join(
            f'<div class="fact"><b class="num">{escape(r["value"])}</b>'
            f'<span>{escape(r["label"])}</span></div>'
            for r in rows
        )
        return f'<div class="factbar" {anchor}>{facts}</div>'

    if group.layout == "impact":
        cells = "".join(
            f'<div><b>{escape(r["value"])}</b><span>{escape(r["label"])}</span></div>'
            for r in rows
        )
        heading = escape(title or i18n.term("metrics.impact", lang))
        note = f'<p class="mgroup-note">{escape(caption)}</p>' if caption else ""
        return (f'<div class="callout" {anchor}><span class="label">{heading}</span>'
                f'<div class="callout-grid">{cells}</div>{note}</div>')

    # Only grow the columns the metrics actually fill in, so a plain
    # label/value table carries no empty headers.
    has_baseline = any(r["baseline"] for r in rows)
    has_delta = any(r["delta"] for r in rows)
    has_note = any(r["note"] for r in rows)

    headers = [i18n.term("metrics.metric", lang)]
    if has_baseline:
        headers.append(i18n.term("metrics.before", lang))
    headers.append(i18n.term("metrics.after" if has_baseline else "metrics.value", lang))
    if has_delta:
        headers.append(i18n.term("metrics.change", lang))
    if has_note:
        headers.append(i18n.term("metrics.note", lang))

    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = []
    for r in rows:
        cells = [f'<th scope="row">{escape(r["label"])}</th>']
        if has_baseline:
            cells.append(f'<td class="was">{escape(r["baseline"])}</td>')
        cells.append(f'<td class="now">{escape(r["value"])}</td>')
        if has_delta:
            cells.append(f'<td class="delta">{escape(r["delta"])}</td>')
        if has_note:
            cells.append(f'<td class="note">{escape(r["note"])}</td>')
        body.append(f"<tr>{''.join(cells)}</tr>")

    heading = f'<span class="label mgroup-title">{escape(title)}</span>' if title else ""
    note = f'<p class="mgroup-note">{escape(caption)}</p>' if caption else ""
    return (
        f'<section class="mgroup" {anchor}>{heading}'
        f'<div class="tablewrap"><table class="mtable">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody>"
        f"</table></div>{note}</section>"
    )


class EmbedIndex:
    """Everything one project can place, and what the body actually placed."""

    # `[[asset:…]]` matches any kind; the typed forms also assert the kind.
    ASSET_KINDS = {"asset", "media", "image", "video", "diagram"}
    GROUP_KINDS = {"metrics", "metric", "table"}

    def __init__(self, project, lang: str | None = None, request=None):
        self.project = project
        self.lang = lang or getattr(project, "language", None) or i18n.default()
        self.request = request
        self.assets = list(project.assets.all())
        self.groups = list(project.metric_groups.all())
        self._assets = {a.ref: a for a in self.assets if a.ref}
        self._groups = {g.ref: g for g in self.groups if g.ref}
        self.placed: set[str] = set()

    def absolute(self, url: str) -> str:
        """Make a local /media/ path absolute; an S3 signature already is."""
        if not url or not self.request or url.startswith(("http://", "https://", "//")):
            return url
        return self.request.build_absolute_uri(url)

    def resolve(self, kind: str, ref: str) -> str | None:
        if kind in self.ASSET_KINDS:
            asset = self._assets.get(ref)
            if asset is None:
                return None
            # `[[video:x]]` pointing at an image is a mistake worth surfacing.
            if kind in {"image", "video", "diagram"} and asset.kind != kind:
                return None
            self.placed.add(f"asset:{ref}")
            return asset_html(asset, self.lang, self.absolute)

        if kind in self.GROUP_KINDS:
            group = self._groups.get(ref)
            if group is None:
                return None
            self.placed.add(f"metrics:{ref}")
            return group_html(group, self.lang)

        return None

    def is_placed(self, obj) -> bool:
        return f"{obj.EMBED_KIND}:{obj.ref}" in self.placed

    def render(self) -> Rendered:
        """The body, with placed embeds inline and unplaced ones appended."""
        body = render(self.project.tr("body_md", self.lang), self.resolve)
        return Rendered(body.html + self.trailing_html(), body.toc)

    def trailing_html(self) -> str:
        """Whatever the body never named, in CMS order. Fact bars are excluded —
        they belong above the title and go out as data, not markup."""
        parts = [
            group_html(g, self.lang)
            for g in self.groups
            if g.layout != "facts" and not self.is_placed(g)
        ]
        parts += [
            asset_html(a, self.lang, self.absolute)
            for a in self.assets
            if not self.is_placed(a)
        ]
        return "".join(p for p in parts if p)

    def facts(self) -> list[dict]:
        """Metrics for the bar under the title — unplaced fact groups only."""
        out = []
        for group in self.groups:
            if group.layout != "facts" or self.is_placed(group):
                continue
            out += [
                {"label": m.tr("label", self.lang), "value": m.tr("value", self.lang),
                 "ref": m.ref}
                for m in group.ordered_metrics()
            ]
        return out

    def groups_json(self) -> list[dict]:
        """Every table, placed or not — enough for a client to render its own."""
        return [
            {
                "ref": g.ref,
                "shortcode": g.shortcode,
                "title": g.tr("title", self.lang),
                "caption": g.tr("caption", self.lang),
                "layout": g.layout,
                "placed": self.is_placed(g),
                "metrics": [
                    {"ref": m.ref, **_cells(m, self.lang)} for m in g.ordered_metrics()
                ],
            }
            for g in self.groups
        ]

    def assets_json(self) -> list[dict]:
        return [
            {
                "ref": a.ref,
                "shortcode": a.shortcode,
                "kind": a.kind,
                "ratio": a.ratio,
                "url": self.absolute(a.url),
                "poster": self.absolute(a.poster_url),
                "caption": a.tr("caption", self.lang),
                "alt": a.tr("alt", self.lang),
                "placed": self.is_placed(a),
            }
            for a in self.assets
        ]


def render_body(project, lang: str | None = None, request=None) -> Rendered:
    """Convenience for callers that only want the HTML (the admin, the model)."""
    return EmbedIndex(project, lang, request).render()
