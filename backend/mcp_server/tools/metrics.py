"""Write tools for metrics and the tables that gather them."""
from __future__ import annotations

from portfolio.models import Metric, MetricGroup, MetricGroupItem

from . import ToolError, tool
from . import common

_METRIC_FIELDS = {
    "label": {"type": "string", "maxLength": 60, "description": "e.g. Warehouse spend"},
    "value": {"type": "string", "maxLength": 40, "description": "e.g. -38%"},
    "baseline": {"type": "string", "maxLength": 40,
                 "description": "The 'before' column, if the table has one."},
    "delta": {"type": "string", "maxLength": 40, "description": "The 'change' column."},
    "note": {"type": "string", "maxLength": 160},
    "ref": {"type": "string", "description": "Stable handle. Generated if omitted."},
    "language": {"type": "string"},
}

_GROUP_FIELDS = {
    "layout": {"type": "string", "enum": common.CHOICES["metric_group_layout"],
               "description": "facts is the bar under the title, impact the "
                              "callout, table a comparison."},
    "title": {"type": "string", "maxLength": 120},
    "caption": {"type": "string", "maxLength": 240},
    "ref": {"type": "string", "description": "Readable handles work well: latency, cost."},
    "order": {"type": "integer"},
    "language": {"type": "string"},
}


@tool(
    name="create_metric",
    title="Create a metric",
    description="""
    One number in a project's library. A metric is not visible on its own: add it
    to a metric group with set_group_metrics, or name it in
    headline_metric_value on the project.
    """,
    schema={
        "properties": {"project": {"type": "string", "description": "Project slug."},
                       **_METRIC_FIELDS},
        "required": ["project", "label", "value"],
    },
)
def create_metric(args, ctx):
    project = common.get_project(args["project"])
    common.check_language(args.get("language"))
    metric = Metric(
        project=project, **{k: v for k, v in args.items() if k in common.METRIC_WRITABLE}
    )
    metric.full_clean(exclude=["ref"])
    metric.save()
    return {"created": True, "project": project.slug, **common.metric_source(metric)}


@tool(
    name="update_metric",
    title="Update a metric",
    idempotent=True,
    description="Edit one metric by its ref. Only the fields you pass are touched.",
    schema={
        "properties": {
            "ref": {"type": "string"},
            "fields": {"type": "object", "properties": _METRIC_FIELDS,
                       "additionalProperties": False},
        },
        "required": ["ref", "fields"],
    },
)
def update_metric(args, ctx):
    metric = common.get_metric(args["ref"])
    fields = args.get("fields") or {}
    common.check_language(fields.get("language"))
    changed = common.apply_fields(metric, fields, common.METRIC_WRITABLE)
    if changed:
        metric.full_clean()
        metric.save()
    return {"changed": changed, **common.metric_source(metric)}


@tool(
    name="create_metric_group",
    title="Create a metric table",
    description="""
    A table of metrics. Returns the shortcode: put it on its own line in body_md
    to place the table there. A table the body never names still renders, after
    the body, except a facts bar which renders above the title.
    """,
    schema={
        "properties": {"project": {"type": "string", "description": "Project slug."},
                       **_GROUP_FIELDS,
                       "metric_refs": {"type": "array", "items": {"type": "string"},
                                       "description": "Metrics to put in it, in order."}},
        "required": ["project", "layout"],
    },
)
def create_metric_group(args, ctx):
    project = common.get_project(args["project"])
    common.check_language(args.get("language"))
    group = MetricGroup(
        project=project, **{k: v for k, v in args.items() if k in common.GROUP_WRITABLE}
    )
    group.full_clean(exclude=["ref"])
    group.save()

    refs = args.get("metric_refs") or []
    if refs:
        _set_items(group, refs, project)

    return {
        "created": True,
        "project": project.slug,
        "ref": group.ref,
        "shortcode": group.shortcode,
        "layout": group.layout,
        "metric_refs": [m.ref for m in group.ordered_metrics()],
        "next": f"Place it by putting {group.shortcode} on its own line in body_md.",
    }


@tool(
    name="update_metric_group",
    title="Update a metric table",
    idempotent=True,
    description="Edit a table's layout, title, caption, ref or order.",
    schema={
        "properties": {
            "project": {"type": "string"},
            "ref": {"type": "string"},
            "fields": {"type": "object", "properties": _GROUP_FIELDS,
                       "additionalProperties": False},
        },
        "required": ["project", "ref", "fields"],
    },
)
def update_metric_group(args, ctx):
    project = common.get_project(args["project"])
    group = common.get_group(project, args["ref"])
    fields = args.get("fields") or {}
    common.check_language(fields.get("language"))
    old_shortcode = group.shortcode

    changed = common.apply_fields(group, fields, common.GROUP_WRITABLE)
    if changed:
        group.full_clean()
        group.save()

    result = {"changed": changed, "ref": group.ref, "shortcode": group.shortcode}
    if "ref" in changed:
        result["warning"] = (
            f"The ref changed, so {old_shortcode} in any body no longer resolves. "
            f"Replace it with {group.shortcode}."
        )
    return result


@tool(
    name="set_group_metrics",
    title="Set the metrics in a table",
    idempotent=True,
    description="""
    Replace a table's contents with this exact list of metric refs, in this order.
    Pass an empty list to empty the table; an empty table renders nothing.
    """,
    schema={
        "properties": {
            "project": {"type": "string"},
            "ref": {"type": "string", "description": "The metric group's ref."},
            "metric_refs": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["project", "ref", "metric_refs"],
    },
)
def set_group_metrics(args, ctx):
    project = common.get_project(args["project"])
    group = common.get_group(project, args["ref"])
    _set_items(group, args["metric_refs"], project)
    return {
        "ref": group.ref,
        "shortcode": group.shortcode,
        "metric_refs": [m.ref for m in group.ordered_metrics()],
    }


def _set_items(group: MetricGroup, refs, project):
    metrics = []
    for ref in refs:
        metric = Metric.objects.filter(ref=ref).first()
        if metric is None:
            raise ToolError(f"No metric with ref {ref!r}.")
        if metric.project_id not in (None, project.pk):
            raise ToolError(
                f"Metric {ref!r} belongs to another project; a table can only "
                f"gather metrics from its own project or the shared library."
            )
        metrics.append(metric)

    seen = [m.ref for m in metrics]
    if len(set(seen)) != len(seen):
        raise ToolError("A metric can only appear once in a table.")

    group.items.all().delete()
    MetricGroupItem.objects.bulk_create(
        [MetricGroupItem(group=group, metric=m, order=i)
         for i, m in enumerate(metrics)]
    )
