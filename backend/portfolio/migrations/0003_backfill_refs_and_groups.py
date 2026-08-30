"""Give every embeddable row a ref, and turn `Metric.placement` into tables.

A metric used to know where it went; now a MetricGroup decides which table it
belongs to and the body decides where that table lands. The two old placement
buckets become two groups per project, so the page renders unchanged.
"""
from __future__ import annotations

import hashlib
import uuid

from django.db import migrations

REF_LENGTH = 8


def _unique_ref(kind: str, seed: str, taken: set[str]) -> str:
    """The same short sha the models generate, but without the model methods."""
    for attempt in range(32):
        candidate = hashlib.sha1(f"{kind}:{seed}:{attempt}".encode()).hexdigest()[:REF_LENGTH]
        if candidate not in taken:
            taken.add(candidate)
            return candidate
    fallback = uuid.uuid4().hex[:REF_LENGTH]
    taken.add(fallback)
    return fallback


def forward(apps, schema_editor):
    Project = apps.get_model("portfolio", "Project")
    Metric = apps.get_model("portfolio", "Metric")
    MetricGroup = apps.get_model("portfolio", "MetricGroup")
    MetricGroupItem = apps.get_model("portfolio", "MetricGroupItem")
    Asset = apps.get_model("portfolio", "Asset")

    # Metric refs are unique across the table.
    taken = {m.ref for m in Metric.objects.exclude(ref="") if m.ref}
    for metric in Metric.objects.filter(ref="").iterator():
        metric.ref = _unique_ref("metric", f"{metric.project_id}:{metric.label}:{metric.value}", taken)
        metric.save(update_fields=["ref"])

    # Asset refs only need to be unique within their project.
    per_project: dict[int, set[str]] = {}
    for asset in Asset.objects.filter(ref="").order_by("project_id", "order", "id").iterator():
        taken = per_project.setdefault(asset.project_id, set())
        name = getattr(asset.video if asset.kind == "video" else asset.image, "name", "") or ""
        seed = f"{asset.project_id}:{asset.kind}:{name}:{asset.caption}:{asset.order}"
        asset.ref = _unique_ref("asset", seed, taken)
        asset.save(update_fields=["ref"])

    # One group per old placement bucket.
    layouts = [("facts", "facts", 0), ("impact", "impact", 1)]
    for project in Project.objects.all().iterator():
        taken = set()
        for placement, layout, order in layouts:
            metrics = list(
                Metric.objects.filter(project=project, placement=placement).order_by("order", "id")
            )
            if not metrics:
                continue
            group = MetricGroup.objects.create(
                project=project,
                layout=layout,
                title="",
                ref=_unique_ref("metrics", f"{project.pk}:{layout}", taken),
                order=order,
                language=getattr(project, "language", "en") or "en",
            )
            MetricGroupItem.objects.bulk_create(
                MetricGroupItem(group=group, metric=metric, order=index)
                for index, metric in enumerate(metrics)
            )


def backward(apps, schema_editor):
    """Put the placement back on the metric and drop the groups."""
    Metric = apps.get_model("portfolio", "Metric")
    MetricGroup = apps.get_model("portfolio", "MetricGroup")
    MetricGroupItem = apps.get_model("portfolio", "MetricGroupItem")

    for item in MetricGroupItem.objects.select_related("group", "metric").iterator():
        placement = "facts" if item.group.layout == "facts" else "impact"
        Metric.objects.filter(pk=item.metric_id).update(placement=placement, order=item.order)
    MetricGroup.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0002_content_refs_translations_metric_groups"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
