"""Content model for the portfolio.

    SiteProfile   hero, about and contact — one row, site-wide
    Capability    one card in "What I run"
    Project       a card in the list, and the whole detail page
    Metric        one number, reusable
    MetricGroup   a table of metrics: fact bar, impact callout or comparison
    Asset         an image or video
    Translation   any field above, in another language

Two mechanisms are worth knowing before reading on:

Refs. Assets and metric groups have a short handle, so a markdown body can
place them exactly where they belong with `[[asset:a1b2c3d4]]`. Anything the
body never names is appended after it.

Translations. One generic Translation row holds (object, language, field,
value), so a new language or a newly translatable field needs no migration.
"""
from __future__ import annotations

import hashlib
import uuid

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from .i18n import Language, default as default_language

REF_LENGTH = 8


class Domain(models.TextChoices):
    STREAMING = "streaming", "Streaming"
    BATCH = "batch", "Batch"
    AI_ML = "ai_ml", "AI / ML"
    INFRA = "infra", "Infrastructure"


class Status(models.TextChoices):
    LIVE = "live", "In production"
    ARCHIVED = "archived", "Archived"
    WIP = "wip", "In progress"


class Translation(models.Model):
    """One field of one row, in one language. Generic on purpose: per-model
    translation tables would mean a migration per translatable field."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    lang = models.CharField(max_length=5, choices=Language.choices)
    field = models.CharField(max_length=40, help_text="The field being translated.")
    value = models.TextField(blank=True, help_text="Leave empty to fall back to the original.")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["lang", "field"]
        indexes = [models.Index(fields=["content_type", "object_id", "lang"])]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "lang", "field"],
                name="unique_translation_per_field",
            )
        ]

    def __str__(self) -> str:
        return f"{self.lang}:{self.field}"


class Translatable(models.Model):
    """Mixin: `language` says what the row itself is written in, `tr()` reads it back."""

    TRANSLATABLE_FIELDS: tuple[str, ...] = ()

    language = models.CharField(
        max_length=5, choices=Language.choices, default=Language.EN,
        help_text="The language these fields are written in. Others go in Translations.",
    )
    translations = GenericRelation(
        Translation, content_type_field="content_type", object_id_field="object_id",
    )

    class Meta:
        abstract = True

    def _translation_map(self) -> dict[tuple[str, str], str]:
        """(lang, field) -> value, cached per instance. Reads translations.all(),
        so prefetch_related("translations") keeps a page to one extra query."""
        cached = getattr(self, "_tr_cache", None)
        if cached is None:
            cached = {
                (t.lang, t.field): t.value
                for t in self.translations.all()
                if t.value and t.value.strip()
            }
            self._tr_cache = cached
        return cached

    def tr(self, field: str, lang: str | None = None):
        """The value of `field` in `lang`, falling back to the row's own text."""
        original = getattr(self, field, "")
        if not lang or lang == self.language:
            return original
        return self._translation_map().get((lang, field)) or original

    def translated(self, lang: str | None = None) -> dict[str, str]:
        """Every translatable field at once, for building a serialized dict."""
        return {name: self.tr(name, lang) for name in self.TRANSLATABLE_FIELDS}

    @property
    def translated_languages(self) -> list[str]:
        return sorted({lang for lang, _ in self._translation_map()})


class Embeddable(models.Model):
    """Mixin: a short, stable handle the markdown body can point at.

    `ref` is generated as a truncated hash, but it is an editable slug — rename
    it to something readable like `latency` whenever that helps.
    """

    EMBED_KIND = "embed"

    ref = models.SlugField(
        max_length=40, blank=True,
        help_text="Short handle used by the body: [[kind:ref]]. Generated if left blank.",
    )

    class Meta:
        abstract = True

    def _ref_seed(self) -> str:
        """Content the generated hash is derived from. Overridden per model."""
        return uuid.uuid4().hex

    def _ref_scope(self):
        """The rows this ref must be unique among."""
        return type(self)._default_manager.all()

    def generate_ref(self) -> str:
        for attempt in range(32):
            seed = f"{self.EMBED_KIND}:{self._ref_seed()}:{attempt}".encode()
            candidate = hashlib.sha1(seed).hexdigest()[:REF_LENGTH]
            if not self._ref_scope().exclude(pk=self.pk).filter(ref=candidate).exists():
                return candidate
        return uuid.uuid4().hex[:REF_LENGTH]

    def save(self, *args, **kwargs):
        if not self.ref:
            self.ref = self.generate_ref()
        return super().save(*args, **kwargs)

    @property
    def shortcode(self) -> str:
        """Paste this into a project body to place the thing exactly there."""
        return f"[[{self.EMBED_KIND}:{self.ref}]]"


class SiteProfile(Translatable):
    """Singleton: everything the landing page needs above the project list."""

    TRANSLATABLE_FIELDS = (
        "role", "location", "availability", "hero_quote",
        "hero_quote_attribution", "intro", "bio_md",
        "capabilities_title", "capabilities_kicker", "cta_headline",
    )

    name = models.CharField(max_length=120)
    role = models.CharField(max_length=160, help_text="e.g. Data & AI Engineer")
    location = models.CharField(max_length=120, blank=True)
    availability = models.CharField(max_length=120, blank=True)

    hero_quote = models.TextField(help_text="The one line in the hero.")
    hero_quote_attribution = models.CharField(max_length=160, blank=True)

    intro = models.TextField(blank=True, help_text="Short role line under the name.")
    bio_md = models.TextField(blank=True, help_text="Markdown. Shown in About.")
    portrait = models.ImageField(upload_to="profile/", blank=True, null=True)

    capabilities_title = models.CharField(
        max_length=120, blank=True,
        help_text='Heading over the capability cards. Blank keeps the built-in "What I run".',
    )
    capabilities_kicker = models.CharField(
        max_length=60, blank=True, help_text="The small label beside it, e.g. 03 / Capabilities.",
    )
    cta_headline = models.TextField(
        blank=True,
        help_text="The closing line above the contact buttons. A line break is a line "
                  "break; wrap a word in *asterisks* to have it drawn as an outline.",
    )

    email = models.EmailField(blank=True)
    links = models.JSONField(
        default=dict, blank=True,
        help_text='e.g. {"GitHub": "https://…", "LinkedIn": "https://…"}',
    )
    cv = models.FileField(upload_to="cv/", blank=True, null=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "site profile"
        verbose_name_plural = "site profile"

    def __str__(self) -> str:
        return self.name or "Site profile"

    def save(self, *args, **kwargs):
        if not self.pk and SiteProfile.objects.exists():
            raise ValidationError("Only one SiteProfile may exist; edit the existing one.")
        return super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteProfile | None":
        return cls.objects.first()

    def bio_html(self, lang: str | None = None) -> str:
        from .embeds import render_prose
        return render_prose(self.tr("bio_md", lang))


class Capability(Translatable):
    """One card in "What I run" — a slice of the practice, not of a project.

    `tools` is a plain comma-separated string, not a link to Tag: these chips
    are a curated list, while Tags are the facets the project list filters on.
    """

    TRANSLATABLE_FIELDS = ("title", "body", "tools")

    title = models.CharField(max_length=120, help_text="e.g. Ingestion & CDC")
    body = models.TextField(help_text="A sentence or two — it sits in a card.")
    tools = models.CharField(
        max_length=240, blank=True,
        help_text="Comma separated, in the order they should read: Kafka, Debezium, Flink.",
    )
    order = models.IntegerField(default=0, help_text="Lower sorts first.")
    published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name_plural = "capabilities"

    def __str__(self) -> str:
        return self.title

    def tool_list(self, lang: str | None = None) -> list[str]:
        """`tools` as the list of chips the card renders, blanks dropped."""
        return [t.strip() for t in self.tr("tools", lang).split(",") if t.strip()]


class Tag(Translatable):
    """A technology or concept. Drives the stack lists and the filter chips."""

    TRANSLATABLE_FIELDS = ("name",)

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    kind = models.CharField(
        max_length=20, default="tech",
        choices=[("tech", "Technology"), ("concept", "Concept"), ("cloud", "Cloud")],
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)


class Project(Translatable):
    TRANSLATABLE_FIELDS = (
        "title", "summary", "standfirst", "body_md", "role", "client", "team",
        "duration", "cover_alt", "headline_metric_label", "headline_metric_value",
    )

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    domain = models.CharField(max_length=20, choices=Domain.choices, default=Domain.STREAMING)
    year = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.LIVE)

    summary = models.CharField(
        max_length=280,
        help_text="One or two lines. Used on the card / row in the project list.",
    )
    standfirst = models.TextField(
        blank=True,
        help_text="The larger paragraph under the title on the detail page.",
    )
    body_md = models.TextField(
        blank=True,
        help_text="The case study, in markdown. Headings become the page contents. "
                  "Place media and metric tables with [[asset:ref]] / [[metrics:ref]].",
    )

    role = models.CharField(max_length=120, blank=True)
    client = models.CharField(max_length=120, blank=True)
    team = models.CharField(max_length=160, blank=True)
    duration = models.CharField(max_length=120, blank=True)

    cover = models.ImageField(upload_to="projects/covers/", blank=True, null=True)
    cover_alt = models.CharField(max_length=200, blank=True)

    tags = models.ManyToManyField(Tag, related_name="projects", blank=True)

    headline_metric_label = models.CharField(
        max_length=60, blank=True, help_text="e.g. p99 freshness"
    )
    headline_metric_value = models.CharField(max_length=40, blank=True, help_text="e.g. 42s")

    repo_url = models.URLField(blank=True)
    live_url = models.URLField(blank=True)

    featured = models.BooleanField(default=False)
    published = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text="Lower sorts first within a year.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-year", "-created_at"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:180]
        return super().save(*args, **kwargs)

    def render(self, lang: str | None = None):
        """(html, toc, placed refs) for the body. Referenced assets and tables
        land at their shortcode; the rest are appended after the body."""
        from .embeds import render_body
        return render_body(self, lang or self.language)

    @property
    def rendered(self):
        return self.render()

    @property
    def body_html(self) -> str:
        return self.render().html

    @property
    def toc(self) -> list[dict]:
        return self.render().toc


class Metric(Translatable):
    """One number, owned by a project and usable in any table. Kept separate
    from the tables so the same figure can appear in more than one."""

    TRANSLATABLE_FIELDS = ("label", "value", "baseline", "delta", "note")

    project = models.ForeignKey(
        Project, related_name="metrics", on_delete=models.CASCADE,
        null=True, blank=True, help_text="Whose library this belongs to. Optional.",
    )
    ref = models.SlugField(
        max_length=40, unique=True, blank=True,
        help_text="Stable handle, generated if blank.",
    )

    label = models.CharField(max_length=60, help_text="e.g. Warehouse spend")
    value = models.CharField(max_length=40, help_text="e.g. −38%")
    baseline = models.CharField(
        max_length=40, blank=True, help_text="The 'before' column, if the table has one.",
    )
    delta = models.CharField(
        max_length=40, blank=True, help_text="The 'change' column, if the table has one.",
    )
    note = models.CharField(max_length=160, blank=True, help_text="Optional aside.")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.label}: {self.value}"

    def save(self, *args, **kwargs):
        if not self.ref:
            seed = f"metric:{self.project_id}:{self.label}:{self.value}"
            for attempt in range(32):
                candidate = hashlib.sha1(f"{seed}:{attempt}".encode()).hexdigest()[:REF_LENGTH]
                if not Metric.objects.exclude(pk=self.pk).filter(ref=candidate).exists():
                    self.ref = candidate
                    break
            else:
                self.ref = uuid.uuid4().hex[:REF_LENGTH]
        return super().save(*args, **kwargs)


class MetricGroup(Embeddable, Translatable):
    """A table of metrics, placed with `[[metrics:ref]]`.

    `layout` picks the shape, not the position: `facts` is the bar under the
    title, `impact` the callout, `table` a comparison. A group the body never
    names falls back to its natural slot — facts under the title, rest below.
    """

    EMBED_KIND = "metrics"
    TRANSLATABLE_FIELDS = ("title", "caption")

    LAYOUT = [
        ("facts", "Fact bar (under the title)"),
        ("impact", "Impact callout"),
        ("table", "Comparison table"),
    ]

    project = models.ForeignKey(
        Project, related_name="metric_groups", on_delete=models.CASCADE,
        null=True, blank=True,
    )
    title = models.CharField(max_length=120, blank=True, help_text="Heading above the table.")
    caption = models.CharField(max_length=240, blank=True)
    layout = models.CharField(max_length=10, choices=LAYOUT, default="table")
    metrics = models.ManyToManyField(
        Metric, through="MetricGroupItem", related_name="groups", blank=True,
    )
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "ref"], name="unique_group_ref_per_project")
        ]

    def __str__(self) -> str:
        return self.title or f"{self.get_layout_display()} · {self.ref}"

    def _ref_seed(self) -> str:
        return f"{self.project_id}:{self.layout}:{self.title}"

    def _ref_scope(self):
        return MetricGroup.objects.filter(project=self.project)

    def ordered_metrics(self) -> list[Metric]:
        return [item.metric for item in self.items.all()]


class MetricGroupItem(models.Model):
    """The through row: which metric, in which table, in what order."""

    group = models.ForeignKey(MetricGroup, related_name="items", on_delete=models.CASCADE)
    metric = models.ForeignKey(Metric, related_name="memberships", on_delete=models.CASCADE)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["group", "metric"], name="unique_metric_per_group")
        ]

    def __str__(self) -> str:
        return f"{self.group} · {self.metric}"


class Asset(Embeddable, Translatable):
    """An image or a video, placed by ref or appended in order."""

    EMBED_KIND = "asset"
    TRANSLATABLE_FIELDS = ("caption", "alt")

    KIND = [("image", "Image"), ("video", "Video"), ("diagram", "Diagram")]
    RATIO = [("21x9", "21:9"), ("16x9", "16:9"), ("4x3", "4:3"), ("4x5", "4:5"), ("1x1", "1:1")]

    project = models.ForeignKey(Project, related_name="assets", on_delete=models.CASCADE)
    kind = models.CharField(max_length=10, choices=KIND, default="image")
    ratio = models.CharField(max_length=10, choices=RATIO, default="16x9")
    image = models.ImageField(upload_to="projects/assets/", blank=True, null=True)
    video = models.FileField(upload_to="projects/video/", blank=True, null=True)
    poster = models.ImageField(upload_to="projects/posters/", blank=True, null=True)
    caption = models.CharField(max_length=240, blank=True)
    alt = models.CharField(max_length=240, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "ref"], name="unique_asset_ref_per_project")
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.caption or self.ref or self.pk}"

    def _ref_seed(self) -> str:
        name = getattr(self.video if self.kind == "video" else self.image, "name", "") or ""
        return f"{self.project_id}:{self.kind}:{name}:{self.caption}:{self.order}"

    def _ref_scope(self):
        return Asset.objects.filter(project=self.project)

    @property
    def file(self):
        return self.video if self.kind == "video" else self.image

    @property
    def url(self) -> str:
        """Signed and absolute on S3, a /media/ path locally."""
        f = self.file
        return f.url if f else ""

    @property
    def poster_url(self) -> str:
        return self.poster.url if self.poster else ""
