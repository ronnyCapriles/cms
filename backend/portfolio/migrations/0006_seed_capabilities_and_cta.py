"""Move the capability cards and contact headline out of the React bundle and
into the CMS: English on the row, Spanish as Translation rows.

Only blank fields are filled, and cards only seeded when there are none, so
this is a no-op against a site whose author already wrote their own.
"""
from __future__ import annotations

from django.db import migrations

# (order, title, body, tools, {lang: (title, body)})
CAPABILITIES = [
    (
        0,
        "Ingestion & CDC",
        "Change capture, schema drift handling, exactly-once semantics and "
        "replayable backfills.",
        "Kafka, Debezium, Flink, Kinesis",
        {
            "es": (
                "Ingesta y CDC",
                "Captura de cambios, manejo de drift de esquema, semántica "
                "exactly-once y backfills reproducibles.",
            )
        },
    ),
    (
        1,
        "Modelling & lakehouse",
        "Dimensional and semantic layers on open table formats, with tests and "
        "contracts that fail loudly.",
        "dbt, Iceberg, Spark, Snowflake",
        {
            "es": (
                "Modelado y lakehouse",
                "Capas dimensionales y semánticas sobre formatos de tabla abiertos, "
                "con tests y contratos que fallan de forma ruidosa.",
            )
        },
    ),
    (
        2,
        "AI & retrieval",
        "Embedding pipelines, graph + vector retrieval, evaluation harnesses and "
        "cost-aware serving.",
        "LangGraph, pgvector, Neo4j, Ray",
        {
            "es": (
                "IA y recuperación",
                "Pipelines de embeddings, recuperación por grafo + vectores, arneses "
                "de evaluación y serving consciente del costo.",
            )
        },
    ),
]

# field -> (english, {lang: translation})
PROFILE_COPY = {
    "capabilities_title": ("What I run", {"es": "Lo que opero"}),
    "capabilities_kicker": ("03 / Capabilities", {"es": "03 / Capacidades"}),
    "cta_headline": ("Let's move\nsome *data*", {"es": "Movamos\nalgunos *datos*"}),
}


def _translate(Translation, ContentType, obj, field: str, values: dict[str, str]) -> None:
    """Add the non-English versions, without clobbering an existing one."""
    ct = ContentType.objects.get_for_model(obj)
    for lang, value in values.items():
        if lang == obj.language:
            continue
        Translation.objects.get_or_create(
            content_type=ct, object_id=obj.pk, lang=lang, field=field,
            defaults={"value": value},
        )


def forward(apps, schema_editor):
    Capability = apps.get_model("portfolio", "Capability")
    SiteProfile = apps.get_model("portfolio", "SiteProfile")
    Translation = apps.get_model("portfolio", "Translation")
    ContentType = apps.get_model("contenttypes", "ContentType")

    if not Capability.objects.exists():
        for order, title, body, tools, translations in CAPABILITIES:
            cap = Capability.objects.create(
                language="en", order=order, title=title, body=body, tools=tools,
            )
            for lang, (other_title, other_body) in translations.items():
                _translate(Translation, ContentType, cap, "title", {lang: other_title})
                _translate(Translation, ContentType, cap, "body", {lang: other_body})

    profile = SiteProfile.objects.first()
    if profile is None:
        return
    changed = []
    for field, (value, translations) in PROFILE_COPY.items():
        if not getattr(profile, field, ""):
            setattr(profile, field, value)
            changed.append(field)
        _translate(Translation, ContentType, profile, field, translations)
    if changed:
        profile.save(update_fields=changed)


def backward(apps, schema_editor):
    """Drop what this migration wrote; the columns themselves go back in 0005.

    The profile's own text is left alone — it lives in columns 0005 removes —
    but its translations are rows that would otherwise outlive their fields.
    """
    Capability = apps.get_model("portfolio", "Capability")
    SiteProfile = apps.get_model("portfolio", "SiteProfile")
    Translation = apps.get_model("portfolio", "Translation")
    ContentType = apps.get_model("contenttypes", "ContentType")

    seeded = {title for _, title, _, _, _ in CAPABILITIES}
    caps = Capability.objects.filter(title__in=seeded)
    Translation.objects.filter(
        content_type=ContentType.objects.get_for_model(Capability),
        object_id__in=list(caps.values_list("pk", flat=True)),
    ).delete()
    caps.delete()

    Translation.objects.filter(
        content_type=ContentType.objects.get_for_model(SiteProfile),
        field__in=list(PROFILE_COPY),
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0005_capabilities_and_cta"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
