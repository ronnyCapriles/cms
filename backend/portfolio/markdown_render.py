"""Markdown -> HTML for project bodies and the bio, in one place so the admin
preview and the API agree.

Beyond ordinary markdown, a line of its own like `[[asset:9f2a1c07]]` is
replaced by whatever the resolver returns for that (kind, ref). The resolver is
passed in, so this module knows nothing about the content model.
"""
from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field

import markdown
from markdown.extensions import Extension
from markdown.extensions.toc import TocExtension
from markdown.preprocessors import Preprocessor

# Up to three leading spaces: four would be a code block, where a shortcode
# should stay literal text.
EMBED_RE = re.compile(
    r"^ {0,3}\[\[\s*(?P<kind>[a-z][a-z0-9_-]*)\s*:\s*(?P<ref>[A-Za-z0-9_-]+)\s*\]\]\s*$"
)

_EXTENSIONS = [
    "extra",            # tables, fenced code, attr_list, def_list, footnotes
    "sane_lists",
    "smarty",
    "codehilite",
]
_CONFIG = {
    "codehilite": {"guess_lang": False, "css_class": "hl"},
}

# Wide content must scroll inside its own container, never the page body.
_TABLE_RE = re.compile(r"(<table\b(?![^>]*\bclass=)[^>]*>.*?</table>)", re.S)


@dataclass
class Rendered:
    """What a body render produced."""

    html: str = ""
    toc: list[dict] = field(default_factory=list)

    def __iter__(self):
        """Tuple-unpackable: `html, toc = render(...)`."""
        return iter((self.html, self.toc))


class _EmbedPreprocessor(Preprocessor):
    """Swaps `[[kind:ref]]` lines for the resolver's HTML, before parsing."""

    def __init__(self, md, resolver):
        super().__init__(md)
        self.resolver = resolver

    def run(self, lines):
        out: list[str] = []
        for line in lines:
            match = EMBED_RE.match(line)
            if match:
                html = self.resolver(match.group("kind"), match.group("ref"))
                if html:
                    # Blank lines keep it its own block, not part of a paragraph.
                    out += ["", self.md.htmlStash.store(html), ""]
                    continue
                # An unresolved ref stays as written: visible and greppable.
            out.append(line)
        return out


class _EmbedExtension(Extension):
    def __init__(self, resolver):
        super().__init__()
        self.resolver = resolver

    def extendMarkdown(self, md):
        # 24 runs just after fenced_code_block (25), so a shortcode inside a
        # ``` example is already stashed and stays literal.
        md.preprocessors.register(
            _EmbedPreprocessor(md, self.resolver), "portfolio_embed", 24
        )


def render(text: str, resolver=None) -> Rendered:
    """Render markdown. `resolver(kind, ref) -> html | None` places embeds."""
    if not text:
        return Rendered()

    extensions = list(_EXTENSIONS)
    extensions.append(TocExtension(baselevel=2, permalink=False, toc_depth="2-3"))
    if resolver is not None:
        extensions.append(_EmbedExtension(resolver))

    md = markdown.Markdown(extensions=extensions, extension_configs=_CONFIG)
    html = md.convert(text)
    # Only markdown's own tables need wrapping; embeds bring their own.
    html = _TABLE_RE.sub(r'<div class="tablewrap">\1</div>', html)
    toc = [
        {"id": item["id"], "title": _html.unescape(item["name"]), "level": item["level"]}
        for item in _flatten(getattr(md, "toc_tokens", []))
    ]
    return Rendered(html, toc)


def _flatten(tokens):
    for t in tokens:
        yield t
        yield from _flatten(t.get("children", []))
