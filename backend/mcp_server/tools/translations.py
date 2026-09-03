"""Setting and clearing translations.

One tool covers every model because Translation is generic on
(object, language, field, value).
"""
from __future__ import annotations

from portfolio import i18n
from portfolio.models import Translation

from . import ToolError, tool
from . import common


def resolve_target(model: str, identifier=None, project=None):
    """Find the row a translation or deletion refers to."""
    cls = common.TRANSLATABLE_MODELS.get(model)
    if cls is None:
        raise ToolError(
            f"Unknown model {model!r}. One of: {sorted(common.TRANSLATABLE_MODELS)}"
        )

    if model == "site_profile":
        return common.get_profile()

    identifier = str(identifier or "").strip()
    if not identifier:
        raise ToolError(f"{model} needs an identifier.")

    if model == "project":
        return common.get_project(identifier)
    if model == "capability":
        return _by_pk(cls, identifier, model)
    if model == "tag":
        found = cls.objects.filter(slug=identifier).first() or cls.objects.filter(
            name__iexact=identifier
        ).first()
        if found is None:
            raise ToolError(f"No tag matches {identifier!r}.")
        return found
    if model == "metric":
        return common.get_metric(identifier)

    # asset and metric_group refs are only unique within a project.
    if not project:
        found = list(cls.objects.filter(ref=identifier)[:2])
        if not found:
            raise ToolError(f"No {model} with ref {identifier!r}.")
        if len(found) > 1:
            raise ToolError(
                f"More than one {model} uses the ref {identifier!r}. Pass the "
                f"owning project slug as `project`."
            )
        return found[0]

    owner = common.get_project(project)
    if model == "asset":
        return common.get_asset(owner, identifier)
    return common.get_group(owner, identifier)


def _by_pk(cls, identifier, model):
    if not identifier.isdigit():
        raise ToolError(f"{model} is identified by its numeric id.")
    found = cls.objects.filter(pk=int(identifier)).first()
    if found is None:
        raise ToolError(f"No {model} with id {identifier}.")
    return found


@tool(
    name="set_translation",
    title="Translate one field",
    idempotent=True,
    description="""
    Store one field of one row in another language. Any field named in that
    model's translatable field list can be translated; anything left untranslated
    falls back to the original per field, not per row.

    Pass an empty value to clear the translation and fall back again.
    """,
    schema={
        "properties": {
            "model": {"type": "string", "enum": sorted(common.TRANSLATABLE_MODELS)},
            "identifier": {
                "type": "string",
                "description": "Project slug, tag slug, asset/metric/group ref, or a "
                               "numeric id for capability. Omit for site_profile.",
            },
            "project": {"type": "string",
                        "description": "Owning project slug, for asset and metric_group."},
            "lang": {"type": "string", "enum": i18n.available()},
            "field": {"type": "string"},
            "value": {"type": "string"},
        },
        "required": ["model", "lang", "field", "value"],
    },
)
def set_translation(args, ctx):
    target = resolve_target(args["model"], args.get("identifier"), args.get("project"))
    lang = common.check_language(args["lang"])

    field = args["field"]
    if field not in target.TRANSLATABLE_FIELDS:
        raise ToolError(
            f"{field!r} is not translatable on {args['model']}. Translatable: "
            f"{list(target.TRANSLATABLE_FIELDS)}"
        )
    if lang == target.language:
        raise ToolError(
            f"The row is already written in {lang}. Edit the field directly, or "
            f"translate into one of {[l for l in i18n.available() if l != lang]}."
        )

    value = args["value"]
    if not value.strip():
        removed, _ = target.translations.filter(lang=lang, field=field).delete()
        return {"cleared": bool(removed), "lang": lang, "field": field,
                "coverage": target.coverage()}

    Translation.objects.update_or_create(
        content_type=_content_type(target), object_id=target.pk,
        lang=lang, field=field, defaults={"value": value},
    )
    target._tr_cache = None
    return {
        "saved": True, "lang": lang, "field": field, "characters": len(value),
        "coverage": target.coverage(),
    }


def _content_type(obj):
    from django.contrib.contenttypes.models import ContentType

    return ContentType.objects.get_for_model(obj)
