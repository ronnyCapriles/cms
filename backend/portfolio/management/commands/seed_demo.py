"""Load placeholder content.

    python manage.py seed_demo          # create/update demo content
    python manage.py seed_demo --reset  # wipe portfolio content first

Everything here is a stand-in — replace it in /admin, not in this file. The
seed places media and metric tables by ref, and ships Spanish for the one
project it creates, so both mechanisms are visible on a fresh database.
"""
from textwrap import dedent

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from portfolio.models import (
    Asset, Domain, Metric, MetricGroup, MetricGroupItem, Project, SiteProfile,
    Status, Tag, Translation,
)

BODY = dedent("""\
    Placeholder opening paragraph. This whole page renders from one markdown
    field — headings become the on-page contents list, and anything the CMS
    holds can be dropped exactly where it belongs by its ref.

    ## The problem

    Nine transactional databases fed a nightly batch that landed at 04:00. Every
    downstream question — fraud review, inventory, the churn model's features —
    was answering yesterday's version of the business.

    - Nightly batch could not be shortened without doubling warehouse spend.
    - Upstream schema changes broke loads roughly twice a month.
    - No replay path: a bad load meant a manual, unlogged fix.

    > Placeholder pull quote — the sentence someone said in a meeting that
    > reframed the whole project.

    ## Architecture

    Debezium captures the WAL from each source, Kafka holds the log, Flink does
    the light shaping, and Iceberg gives us time travel plus the ability to
    rewrite history when a source lies to us.

    [[asset:diagram]]

    ```python
    def sink(stream: DataStream) -> None:
        (stream
            .key_by(lambda r: r["pk"])
            .process(DedupeByLsn(ttl="6h"))
            .sink_to(iceberg("warehouse.raw.orders", upsert=True)))
    ```

    ## What changed

    Placeholder results narrative. Lead with the number a hiring manager would
    repeat to someone else.

    [[metrics:before-after]]

    The second table is a different cut of the same project — cost rather than
    latency — and it sits here because this is where the argument needs it, not
    because it was added second.

    [[metrics:cost]]

    [[asset:walkthrough]]

    ## What I'd do differently

    Placeholder. This section is worth more than the results section — most
    portfolios skip it, and it is the one interviewers actually probe.

    [[metrics:impact]]
    """)

BODY_ES = dedent("""\
    Párrafo inicial de ejemplo. Toda esta página se renderiza desde un solo
    campo markdown — los encabezados forman el índice lateral, y cualquier
    contenido del CMS se coloca justo donde corresponde usando su ref.

    ## El problema

    Nueve bases transaccionales alimentaban un batch nocturno que llegaba a las
    04:00. Cada pregunta aguas abajo respondía con la versión de ayer del
    negocio.

    - El batch no podía acortarse sin duplicar el gasto del warehouse.
    - Los cambios de esquema rompían las cargas unas dos veces al mes.
    - Sin camino de reproceso: una carga mala significaba un arreglo manual.

    > Cita de ejemplo — la frase que en una reunión reencuadró el proyecto
    > completo.

    ## Arquitectura

    Debezium captura el WAL de cada fuente, Kafka guarda el log, Flink hace el
    modelado ligero e Iceberg aporta viaje en el tiempo.

    [[asset:diagram]]

    ## Lo que cambió

    Narrativa de resultados de ejemplo. Empieza por el número que alguien
    repetiría en otra conversación.

    [[metrics:before-after]]

    La segunda tabla es otro corte del mismo proyecto — costo en vez de
    latencia — y va aquí porque es donde el argumento la necesita.

    [[metrics:cost]]

    [[asset:walkthrough]]

    ## Qué haría distinto

    Ejemplo. Esta sección vale más que la de resultados: casi nadie la escribe y
    es la que de verdad exploran en una entrevista.

    [[metrics:impact]]
    """)

# label, baseline, value, delta — the columns a comparison table can show.
BEFORE_AFTER = [
    ("Ingest latency", "8h 00m", "42s", "−99.9%"),
    ("Backfill (30d)", "manual", "21m", "automated"),
    ("Failed loads / mo", "2.1", "0.0", "−100%"),
]
COST = [
    ("Cost / TB landed", "$41.20", "$25.60", "−38%"),
    ("Idle warehouse credits", "31%", "9%", "−71%"),
]

# One project, because the point is to show the shape. Copy the dict to add more;
# `order` comes from the list position.
PROJECTS = [
    {
        "title": "Realtime CDC to lakehouse", "domain": Domain.STREAMING, "year": 2026,
        "summary": "Change data capture from 9 OLTP sources into an Iceberg lakehouse with "
                   "sub-minute freshness and replayable backfills.",
        "tags": ["Kafka", "Debezium", "Iceberg", "Flink"],
        "metric": ("p99 freshness", "42s"), "featured": True,
        "facts": [("Source systems", "9"), ("Rows / day", "1.4B"), ("p99 freshness", "42s"), ("Duration", "7 mo")],
        "impact": [("Data freshness", "04:00 → 42s"), ("Warehouse spend", "−38%"), ("Schema breakages", "2/mo → 0")],
        "es": {"title": "CDC en tiempo real al lakehouse",
               "summary": "Captura de cambios desde 9 fuentes OLTP hacia un lakehouse Iceberg, "
                          "con frescura de menos de un minuto y backfills reproducibles."},
    },
]

# Spanish for the metric labels. A label with no entry stays in English, which
# is the same fallback real content gets.
LABELS_ES = {
    "Source systems": "Sistemas fuente", "Rows / day": "Filas / día",
    "p99 freshness": "Frescura p99", "Duration": "Duración",
    "Data freshness": "Frescura de los datos",
    "Warehouse spend": "Gasto del warehouse",
    "Schema breakages": "Rupturas de esquema",
    "Ingest latency": "Latencia de ingesta", "Backfill (30d)": "Backfill (30d)",
    "Failed loads / mo": "Cargas fallidas / mes",
    "Cost / TB landed": "Costo / TB aterrizado",
    "Idle warehouse credits": "Créditos ociosos del warehouse",
}
VALUES_ES = {"manual": "manual", "automated": "automatizado"}

# Tables every project gets: ref -> (layout, English title, Spanish title)
GROUPS = {
    "facts": ("facts", "", ""),
    "before-after": ("table", "Before and after", "Antes y después"),
    "cost": ("table", "Cost profile", "Perfil de costo"),
    "impact": ("impact", "Measured impact", "Impacto medido"),
}


def translate(obj, lang, **fields):
    """Write (or update) one row's translations for a language."""
    ct = ContentType.objects.get_for_model(type(obj))
    for field, value in fields.items():
        Translation.objects.update_or_create(
            content_type=ct, object_id=obj.pk, lang=lang, field=field,
            defaults={"value": value},
        )


class Command(BaseCommand):
    help = "Load placeholder portfolio content."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing content first.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["reset"]:
            Project.objects.all().delete()
            Tag.objects.all().delete()
            SiteProfile.objects.all().delete()
            Translation.objects.all().delete()
            self.stdout.write("cleared existing content")

        self.seed_profile()
        for i, spec in enumerate(PROJECTS):
            self.seed_project(i, spec)

        self.stdout.write(self.style.SUCCESS(
            f"seeded {Project.objects.count()} projects, {Tag.objects.count()} tags, "
            f"{MetricGroup.objects.count()} metric tables, "
            f"{Translation.objects.count()} translations"
        ))

    def seed_profile(self):
        profile = SiteProfile.load() or SiteProfile(name="Your name")
        profile.name = "Your name"
        profile.role = "Data & AI Engineer"
        profile.location = "Placeholder — city → remote"
        profile.availability = "Available"
        profile.hero_quote = ("Placeholder quote — the one line you want a hiring manager to "
                              "remember. Replace this text.")
        profile.hero_quote_attribution = "Quote attribution placeholder"
        profile.intro = ("I build the ingestion, modelling and retrieval layers that decide "
                         "whether an AI system is a demo or a dependency.")
        profile.bio_md = dedent("""\
            Placeholder bio. I work on the unglamorous half of AI — **ingestion, contracts,
            lineage and cost** — the parts that decide whether a model in a notebook ever
            becomes a product someone depends on.

            Most of what I build looks like a graph: sources on the left, a warehouse in the
            middle, a retrieval or serving layer on the right, and enough observability in
            between that a 3am page has an obvious answer.
            """)
        profile.email = "you@example.com"
        profile.links = {"GitHub": "https://github.com/you", "LinkedIn": "https://linkedin.com/in/you"}
        profile.save()

        translate(
            profile, "es",
            role="Ingeniero de Datos e IA",
            location="Ejemplo — ciudad → remoto",
            availability="Disponible",
            hero_quote=("Cita de ejemplo — la línea que quieres que recuerde quien te "
                        "entrevista. Reemplaza este texto."),
            hero_quote_attribution="Atribución de ejemplo",
            intro=("Construyo las capas de ingesta, modelado y recuperación que deciden si un "
                   "sistema de IA es un demo o una dependencia."),
            bio_md=dedent("""\
                Bio de ejemplo. Trabajo en la mitad poco glamorosa de la IA — **ingesta,
                contratos, linaje y costo** — las partes que deciden si un modelo en un
                notebook llega a ser un producto del que alguien depende.

                Casi todo lo que construyo se parece a un grafo: fuentes a la izquierda, un
                warehouse en el medio, una capa de recuperación o serving a la derecha, y
                suficiente observabilidad para que una alerta a las 3am tenga respuesta obvia.
                """),
        )

    def seed_project(self, index, spec):
        project, _ = Project.objects.update_or_create(
            slug=spec["title"].lower().replace(" ", "-").replace("+", "plus"),
            defaults={
                "title": spec["title"],
                "domain": spec["domain"],
                "year": spec["year"],
                "status": spec.get("status", Status.LIVE),
                "summary": spec["summary"],
                "standfirst": ("Standfirst placeholder — one or two sentences telling a hiring "
                               "manager what this was and why it mattered, before they decide "
                               "whether to keep reading."),
                "body_md": BODY,
                "role": "Placeholder — lead data engineer",
                "client": "Client placeholder",
                "team": "Placeholder — 4 eng, 1 analyst",
                "duration": "Placeholder — 7 months",
                "headline_metric_label": spec["metric"][0],
                "headline_metric_value": spec["metric"][1],
                "featured": spec.get("featured", False),
                "repo_url": "https://github.com/you/placeholder-repo",
                "live_url": "https://example.com",
                "order": index,
            },
        )
        project.tags.set([Tag.objects.get_or_create(name=n)[0] for n in spec["tags"]])

        translate(
            project, "es",
            body_md=BODY_ES,
            standfirst=("Entradilla de ejemplo — una o dos frases que expliquen qué fue esto y "
                        "por qué importó, antes de que decidan seguir leyendo."),
            role="Ejemplo — ingeniero de datos principal",
            team="Ejemplo — 4 ing., 1 analista",
            duration="Ejemplo — 7 meses",
            **spec["es"],
        )

        self.seed_metrics(project, spec)
        self.seed_assets(project)

    def seed_metrics(self, project, spec):
        """Rebuild this project's metrics and the four tables that arrange them."""
        project.metrics.all().delete()          # cascades the group memberships
        project.metric_groups.all().delete()

        groups = {}
        for order, (ref, (layout, title, title_es)) in enumerate(GROUPS.items()):
            group = MetricGroup.objects.create(
                project=project, ref=ref, layout=layout, title=title, order=order,
            )
            if title_es:
                translate(group, "es", title=title_es)
            groups[ref] = group

        def attach(group, rows):
            """rows: (label, baseline, value, delta)."""
            for position, (label, baseline, value, delta) in enumerate(rows):
                metric = Metric.objects.create(
                    project=project, label=label, value=value,
                    baseline=baseline, delta=delta,
                )
                MetricGroupItem.objects.create(group=group, metric=metric, order=position)
                spanish = {}
                if label in LABELS_ES:
                    spanish["label"] = LABELS_ES[label]
                for field, text in (("value", value), ("baseline", baseline), ("delta", delta)):
                    if text in VALUES_ES:
                        spanish[field] = VALUES_ES[text]
                if spanish:
                    translate(metric, "es", **spanish)

        attach(groups["facts"], [(l, "", v, "") for l, v in spec["facts"]])
        attach(groups["impact"], [(l, "", v, "") for l, v in spec["impact"]])
        attach(groups["before-after"], BEFORE_AFTER)
        attach(groups["cost"], COST)

    def seed_assets(self, project):
        """Two slots with stable refs, so the body can name them."""
        diagram, _ = Asset.objects.update_or_create(
            project=project, ref="diagram",
            defaults={"kind": "diagram", "ratio": "16x9", "order": 0,
                      "caption": "Placeholder — drop your architecture diagram here."},
        )
        walkthrough, _ = Asset.objects.update_or_create(
            project=project, ref="walkthrough",
            defaults={"kind": "video", "ratio": "16x9", "order": 1,
                      "caption": "Placeholder — a 60–90s walkthrough."},
        )
        # Drop anything seeded before refs existed, which would duplicate these.
        Asset.objects.filter(project=project).exclude(
            pk__in=[diagram.pk, walkthrough.pk]
        ).delete()

        translate(diagram, "es", caption="Ejemplo — coloca aquí tu diagrama de arquitectura.")
        translate(walkthrough, "es", caption="Ejemplo — un recorrido de 60–90 s.")
