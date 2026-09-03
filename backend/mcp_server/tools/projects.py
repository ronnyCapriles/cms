"""Write tools for projects, tags, capabilities and the site profile."""
from __future__ import annotations

from django.utils.text import slugify

from portfolio.models import Capability, Project, Tag

from . import ToolError, tool
from . import common

_PROJECT_FIELDS = {
    "title": {"type": "string", "maxLength": 160},
    "slug": {"type": "string", "description": "Generated from the title if omitted."},
    "language": {"type": "string", "description": "What these fields are written in."},
    "summary": {"type": "string", "maxLength": 280,
                "description": "One or two lines, shown on the card."},
    "standfirst": {"type": "string",
                   "description": "The larger paragraph under the title."},
    "body_md": {"type": "string",
                "description": "The case study in markdown. Headings become the "
                               "contents list. Place blocks with [[asset:REF]]."},
    "domain": {"type": "string", "enum": common.CHOICES["domain"]},
    "year": {"type": "integer"},
    "status": {"type": "string", "enum": common.CHOICES["status"]},
    "role": {"type": "string"},
    "client": {"type": "string"},
    "team": {"type": "string"},
    "duration": {"type": "string"},
    "cover_alt": {"type": "string"},
    "headline_metric_label": {"type": "string", "maxLength": 60},
    "headline_metric_value": {"type": "string", "maxLength": 40},
    "repo_url": {"type": "string"},
    "live_url": {"type": "string"},
    "featured": {"type": "boolean"},
    "order": {"type": "integer", "description": "Lower sorts first within a year."},
}


@tool(
    name="create_project",
    title="Create a project",
    description="""
    Create a case study. It is always created unpublished; call publish_project
    when it is ready. Returns the slug and the admin URL.
    """,
    schema={
        "properties": {
            **_PROJECT_FIELDS,
            "tags": {"type": "array", "items": {"type": "string"},
                     "description": "Tag slugs or names."},
            "create_missing_tags": {"type": "boolean"},
        },
        "required": ["title", "summary", "year"],
    },
)
def create_project(args, ctx):
    data = {k: v for k, v in args.items() if k in common.PROJECT_WRITABLE}
    common.check_language(data.get("language"))

    slug = data.get("slug") or slugify(str(data["title"]))[:180]
    if Project.objects.filter(slug=slug).exists():
        raise ToolError(
            f"A project already uses the slug {slug!r}. Pass an explicit slug, or "
            f"update_project if you meant to edit the existing one."
        )
    data["slug"] = slug

    tags, created = common.resolve_tags(
        args.get("tags"), bool(args.get("create_missing_tags"))
    )

    project = Project(published=False, **data)
    project.full_clean(exclude=["tags"])
    project.save()
    if tags:
        project.tags.set(tags)

    return {
        "created": True,
        "slug": project.slug,
        "published": False,
        "tags": [t.slug for t in tags],
        "tags_created": created,
        "urls": {"public": project.get_absolute_url(), "admin": common.admin_url(project)},
        "next": "Add metrics and assets, then call publish_project when ready.",
    }


@tool(
    name="update_project",
    title="Update a project",
    idempotent=True,
    description="""
    Change any writable field of a case study. Only the fields you pass are
    touched. `published` is not writable here. Retitling is safe: the slug is
    only ever generated when blank, so a live URL never moves.
    """,
    schema={
        "properties": {
            "slug": {"type": "string", "description": "Which project to edit."},
            "fields": {
                "type": "object",
                "properties": {k: v for k, v in _PROJECT_FIELDS.items() if k != "slug"},
                "additionalProperties": False,
            },
        },
        "required": ["slug", "fields"],
    },
)
def update_project(args, ctx):
    project = common.get_project(args["slug"])
    fields = args.get("fields") or {}
    common.check_language(fields.get("language"))

    changed = common.apply_fields(project, fields, common.PROJECT_WRITABLE - {"slug"})
    if changed:
        project.full_clean(exclude=["tags"])
        project.save()

    return {"slug": project.slug, "changed": changed,
            "urls": {"admin": common.admin_url(project)}}


@tool(
    name="set_project_tags",
    title="Set a project's tags",
    idempotent=True,
    description="Replace the tag list on a project. Pass an empty list to clear it.",
    schema={
        "properties": {
            "slug": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "create_missing": {"type": "boolean"},
        },
        "required": ["slug", "tags"],
    },
)
def set_project_tags(args, ctx):
    project = common.get_project(args["slug"])
    tags, created = common.resolve_tags(args["tags"], bool(args.get("create_missing")))
    project.tags.set(tags)
    return {"slug": project.slug, "tags": [t.slug for t in tags], "tags_created": created}


@tool(
    name="publish_project",
    title="Publish a project",
    idempotent=True,
    description="""
    Make a case study visible on the site. This is the only tool that sets
    published. Confirm with the human before calling it.
    """,
    schema={"properties": {"slug": {"type": "string"}}, "required": ["slug"]},
)
def publish_project(args, ctx):
    project = common.get_project(args["slug"])
    was = project.published
    project.published = True
    project.save(update_fields=["published", "updated_at"])
    return {"slug": project.slug, "published": True, "changed": not was,
            "url": project.get_absolute_url()}


@tool(
    name="unpublish_project",
    title="Unpublish a project",
    idempotent=True,
    description="Hide a case study from the site without deleting it.",
    schema={"properties": {"slug": {"type": "string"}}, "required": ["slug"]},
)
def unpublish_project(args, ctx):
    project = common.get_project(args["slug"])
    was = project.published
    project.published = False
    project.save(update_fields=["published", "updated_at"])
    return {"slug": project.slug, "published": False, "changed": was}


@tool(
    name="create_tag",
    title="Create a tag",
    description="A technology or concept. The slug is generated from the name.",
    schema={
        "properties": {
            "name": {"type": "string", "maxLength": 60},
            "kind": {"type": "string", "enum": common.CHOICES["tag_kind"]},
            "slug": {"type": "string"},
            "language": {"type": "string"},
        },
        "required": ["name"],
    },
)
def create_tag(args, ctx):
    name = args["name"].strip()
    existing = Tag.objects.filter(name__iexact=name).first()
    if existing:
        raise ToolError(f"Tag {name!r} already exists as {existing.slug!r}.")
    common.check_language(args.get("language"))
    tag = Tag(**{k: v for k, v in args.items() if k in common.TAG_WRITABLE})
    tag.full_clean()
    tag.save()
    return {"created": True, "slug": tag.slug, "name": tag.name, "kind": tag.kind}


@tool(
    name="update_site_profile",
    title="Update the site profile",
    idempotent=True,
    description="""
    Edit the single site-wide row: hero, bio, contact and the capability section
    headings. Only the fields you pass are touched.
    """,
    schema={
        "properties": {
            "fields": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "language": {"type": "string"},
                    "role": {"type": "string"},
                    "location": {"type": "string"},
                    "availability": {"type": "string"},
                    "hero_quote": {"type": "string",
                                   "description": "The one line in the hero."},
                    "hero_quote_attribution": {"type": "string"},
                    "intro": {"type": "string"},
                    "bio_md": {"type": "string", "description": "Markdown, shown in About."},
                    "capabilities_title": {"type": "string"},
                    "capabilities_kicker": {"type": "string"},
                    "cta_headline": {
                        "type": "string",
                        "description": "Closing line. A line break is a line break; "
                                       "*asterisks* draw a word as an outline.",
                    },
                    "email": {"type": "string"},
                    "links": {"type": "object",
                              "description": 'e.g. {"GitHub": "https://..."}'},
                },
                "additionalProperties": False,
            },
        },
        "required": ["fields"],
    },
)
def update_site_profile(args, ctx):
    profile = common.get_profile()
    fields = args.get("fields") or {}
    common.check_language(fields.get("language"))
    changed = common.apply_fields(profile, fields, common.PROFILE_WRITABLE)
    if changed:
        profile.full_clean()
        profile.save()
    return {"changed": changed, "urls": {"admin": common.admin_url(profile)}}


_CAPABILITY_FIELDS = {
    "title": {"type": "string", "maxLength": 120},
    "body": {"type": "string", "description": "A sentence or two; it sits in a card."},
    "tools": {"type": "string",
              "description": "Comma separated, in reading order: Kafka, Debezium, Flink."},
    "order": {"type": "integer", "description": "Lower sorts first."},
    "published": {"type": "boolean"},
    "language": {"type": "string"},
}


@tool(
    name="create_capability",
    title="Create a capability card",
    description='One card in the "What I run" section.',
    schema={"properties": _CAPABILITY_FIELDS, "required": ["title", "body"]},
)
def create_capability(args, ctx):
    common.check_language(args.get("language"))
    capability = Capability(
        **{k: v for k, v in args.items() if k in common.CAPABILITY_WRITABLE}
    )
    capability.full_clean()
    capability.save()
    return {"created": True, **common.capability_source(capability)}


@tool(
    name="update_capability",
    title="Update a capability card",
    idempotent=True,
    description="Edit one capability card by id. Only the fields you pass are touched.",
    schema={
        "properties": {
            "id": {"type": "integer"},
            "fields": {"type": "object", "properties": _CAPABILITY_FIELDS,
                       "additionalProperties": False},
        },
        "required": ["id", "fields"],
    },
)
def update_capability(args, ctx):
    capability = Capability.objects.filter(pk=args["id"]).first()
    if capability is None:
        raise ToolError(f"No capability with id {args['id']}.")
    fields = args.get("fields") or {}
    common.check_language(fields.get("language"))
    changed = common.apply_fields(capability, fields, common.CAPABILITY_WRITABLE)
    if changed:
        capability.full_clean()
        capability.save()
    return {"changed": changed, **common.capability_source(capability)}


@tool(
    name="delete_content",
    title="Delete a row",
    destructive=True,
    description="""
    Permanently delete one row. Deleting a project also deletes its metrics,
    tables and assets. The identifier must be repeated in `confirm` to guard
    against an accidental call.
    """,
    schema={
        "properties": {
            "model": {"type": "string", "enum": sorted(common.DELETABLE_MODELS)},
            "identifier": {
                "type": "string",
                "description": "Project slug, tag slug, asset/metric/group ref, or "
                               "a primary key.",
            },
            "project": {"type": "string",
                        "description": "Owning project slug, for asset and metric_group."},
            "confirm": {"type": "string",
                        "description": "Repeat the identifier exactly."},
        },
        "required": ["model", "identifier", "confirm"],
    },
)
def delete_content(args, ctx):
    from .translations import resolve_target

    if args["confirm"] != args["identifier"]:
        raise ToolError(
            "confirm must repeat identifier exactly. Nothing was deleted."
        )
    if args["model"] not in common.DELETABLE_MODELS:
        raise ToolError(f"{args['model']} cannot be deleted through this API.")

    target = resolve_target(args["model"], args["identifier"], args.get("project"))
    label = str(target)
    deleted, per_model = target.delete()
    return {"deleted": deleted, "what": label, "by_model": per_model}
