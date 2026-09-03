"""Read tools: discovery, inspection and preview."""
from __future__ import annotations

from django.db.models import Q

from portfolio import i18n
from portfolio.markdown_render import EMBED_RE
from portfolio.models import Capability, Project, SiteProfile, Tag

from . import Scope, tool
from . import common

READ = Scope.READ


@tool(
    name="describe_content_model",
    title="Describe the content model",
    scope=READ, idempotent=True,
    description="""
    The shape of the CMS: models, writable fields, choice values, the languages
    configured and the shortcode syntax. Call this before the first edit of a
    session; it saves guessing at field names.
    """,
    schema={"properties": {}},
)
def describe_content_model(args, ctx):
    return {
        "languages": {
            "available": i18n.available(),
            "default": i18n.default(),
            "how": "Write a row in one language, then set_translation per field "
                   "for the others. Nothing needs a migration.",
        },
        "choices": common.CHOICES,
        "shortcodes": {
            "syntax": "[[asset:REF]] or [[metrics:REF]] alone on a line of body_md",
            "typed_asset_forms": ["image", "video", "diagram"],
            "behaviour": "A shortcode moves a block to that spot. Anything never "
                         "referenced still renders, appended after the body. Fact "
                         "bars are the exception: they render above the title.",
        },
        "models": {
            "site_profile": {
                "what": "Singleton. Hero, about, contact, capability headings.",
                "writable": sorted(common.PROFILE_WRITABLE),
            },
            "capability": {
                "what": "One card in the capabilities section.",
                "writable": sorted(common.CAPABILITY_WRITABLE),
            },
            "tag": {
                "what": "Technology or concept. Drives the filter chips.",
                "writable": sorted(common.TAG_WRITABLE),
            },
            "project": {
                "what": "A case study: the card in the list and the detail page.",
                "writable": sorted(common.PROJECT_WRITABLE),
                "notes": "published is not writable here; use publish_project. The "
                         "slug is set from the title only when blank, so retitling "
                         "never breaks a live URL.",
            },
            "metric": {
                "what": "One number, owned by a project, reusable across tables.",
                "writable": sorted(common.METRIC_WRITABLE),
            },
            "metric_group": {
                "what": "A table of metrics. facts is the bar under the title, "
                        "impact the callout, table a comparison.",
                "writable": sorted(common.GROUP_WRITABLE),
            },
            "asset": {
                "what": "An image or video belonging to a project.",
                "writable": sorted(common.ASSET_WRITABLE),
            },
        },
    }


@tool(
    name="list_projects",
    title="List projects",
    scope=READ, idempotent=True,
    description="""
    Case studies including unpublished drafts. Every filter is optional and they
    compose.
    """,
    schema={
        "properties": {
            "published": {"type": "boolean", "description": "Omit to get both."},
            "domain": {"type": "string", "enum": common.CHOICES["domain"]},
            "status": {"type": "string", "enum": common.CHOICES["status"]},
            "tag": {"type": "string", "description": "Tag slug."},
            "year": {"type": "integer"},
            "featured": {"type": "boolean"},
            "q": {"type": "string", "description": "Substring of title or summary."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
    },
)
def list_projects(args, ctx):
    qs = Project.objects.prefetch_related("translations", "tags")

    if "published" in args:
        qs = qs.filter(published=bool(args["published"]))
    if args.get("domain"):
        qs = qs.filter(domain=args["domain"])
    if args.get("status"):
        qs = qs.filter(status=args["status"])
    if args.get("tag"):
        qs = qs.filter(tags__slug=args["tag"])
    if args.get("year"):
        qs = qs.filter(year=int(args["year"]))
    if "featured" in args:
        qs = qs.filter(featured=bool(args["featured"]))
    if args.get("q"):
        needle = args["q"].strip()
        qs = qs.filter(Q(title__icontains=needle) | Q(summary__icontains=needle))

    qs = qs.distinct()
    limit = int(args.get("limit") or 50)
    return {"count": qs.count(), "results": [common.project_card(p) for p in qs[:limit]]}


@tool(
    name="get_project",
    title="Get a project",
    scope=READ, idempotent=True,
    description="""
    One case study in source form: body_md rather than rendered HTML, plus its
    metrics, tables, assets, their shortcodes and its translations. Read this
    before editing anything.
    """,
    schema={"properties": {"slug": {"type": "string"}}, "required": ["slug"]},
)
def get_project_tool(args, ctx):
    return common.project_source(common.get_project(args["slug"]), ctx.request)


@tool(
    name="get_site_profile",
    title="Get the site profile",
    scope=READ, idempotent=True,
    description="The single site-wide row: hero, bio, contact, section headings.",
    schema={"properties": {}},
)
def get_site_profile(args, ctx):
    return common.profile_source(common.get_profile(), ctx.request)


@tool(
    name="list_capabilities",
    title="List capability cards",
    scope=READ, idempotent=True,
    description='The cards in the "What I run" section, in display order.',
    schema={"properties": {"published": {"type": "boolean"}}},
)
def list_capabilities(args, ctx):
    qs = Capability.objects.prefetch_related("translations")
    if "published" in args:
        qs = qs.filter(published=bool(args["published"]))
    return {"results": [common.capability_source(c) for c in qs]}


@tool(
    name="list_tags",
    title="List tags",
    scope=READ, idempotent=True,
    description="Every tag with its project count. Reuse these rather than "
                "minting near-duplicates.",
    schema={"properties": {}},
)
def list_tags(args, ctx):
    return {
        "results": [
            {"slug": t.slug, "name": t.name, "kind": t.kind,
             "projects": len(t.projects.all()), "language": t.language}
            for t in Tag.objects.prefetch_related("projects", "translations")
        ]
    }


@tool(
    name="list_translations",
    title="List translations of one row",
    scope=READ, idempotent=True,
    description="Every stored translation for one object, grouped by language.",
    schema={
        "properties": {
            "model": {"type": "string", "enum": sorted(common.TRANSLATABLE_MODELS)},
            "identifier": {
                "type": "string",
                "description": "Project slug, asset/metric/group ref, tag slug, or a "
                               "primary key. Omit for site_profile.",
            },
        },
        "required": ["model"],
    },
)
def list_translations(args, ctx):
    from .translations import resolve_target

    target = resolve_target(args["model"], args.get("identifier"))
    return {
        "model": args["model"],
        "language": target.language,
        "translatable_fields": list(target.TRANSLATABLE_FIELDS),
        "translations": common.translations_of(target),
        "coverage": target.coverage(),
    }


@tool(
    name="translation_coverage",
    title="Translation coverage",
    scope=READ, idempotent=True,
    description="""
    What is still untranslated, across the site or within one project. A field
    only counts as missing when the original actually fills it.
    """,
    schema={"properties": {"slug": {"type": "string",
                                    "description": "Limit to one project."}}},
)
def translation_coverage(args, ctx):
    if args.get("slug"):
        project = common.get_project(args["slug"])
        rows = [("project", project.slug, project.coverage())]
        rows += [("asset", a.ref, a.coverage()) for a in project.assets.all()]
        rows += [("metric", m.ref, m.coverage()) for m in project.metrics.all()]
        rows += [("metric_group", g.ref, g.coverage())
                 for g in project.metric_groups.all()]
    else:
        rows = [("project", p.slug, p.coverage())
                for p in Project.objects.prefetch_related("translations")]
        rows += [("capability", str(c.pk), c.coverage())
                 for c in Capability.objects.prefetch_related("translations")]
        profile = SiteProfile.objects.prefetch_related("translations").first()
        if profile is not None:
            rows.append(("site_profile", "", profile.coverage()))

    incomplete = [
        {"model": model, "identifier": ident, "lang": row["lang"],
         "done": row["done"], "total": row["total"], "missing": row["missing"]}
        for model, ident, cov in rows for row in cov if row["missing"]
    ]
    return {"incomplete": incomplete, "complete": not incomplete}


@tool(
    name="render_preview",
    title="Preview the rendered body",
    scope=READ, idempotent=True,
    description="""
    Render a project the way the site will, in one language. Use it to check that
    shortcodes resolved: anything under unresolved_shortcodes is a typo, because
    an unknown ref stays on the page as literal text.
    """,
    schema={
        "properties": {"slug": {"type": "string"}, "lang": {"type": "string"}},
        "required": ["slug"],
    },
)
def render_preview(args, ctx):
    lang = common.check_language(args.get("lang"))
    project = common.get_project(args["slug"])
    index = common.render_index(project, lang, ctx.request)
    rendered = index.render()

    known = {a.shortcode for a in project.assets.all()}
    known |= {g.shortcode for g in project.metric_groups.all()}

    return {
        "slug": project.slug,
        "lang": lang or project.language,
        "html": rendered.html,
        "toc": rendered.toc,
        "facts": index.facts(),
        "placed": sorted(index.placed),
        "unresolved_shortcodes": _unresolved(project.tr("body_md", lang) or "", known),
    }


def _unresolved(body: str, known: set[str]) -> list[str]:
    found = set()
    for line in body.splitlines():
        match = EMBED_RE.match(line)
        if match and match.group(0).strip() not in known:
            found.add(match.group(0).strip())
    return sorted(found)
