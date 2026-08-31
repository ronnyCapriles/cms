# Portfolio CMS — Dataflow

A Django CMS that publishes markdown case studies to a React front end, with the
content translated per row rather than per template.

```
backend/         Django: content model, admin, JSON API
frontend/        Vite + React, built into Django's staticfiles
docker/          container entrypoint
deploy/          the updater the instance runs on a timer
```

## Run it

```bash
cp .env.example .env          # DJANGO_SECRET_KEY is the only one worth setting
docker compose up --build
```

`http://localhost:8000` — the site · `/admin/` — write content ·
`/api/projects/` — what the front end reads.

Seed the placeholder content and make a login:

```bash
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py createsuperuser
```

`seed_demo --reset` wipes and reloads it. The seed makes one example project,
in English and Spanish, so the language toggle has something to switch to.

### Hot reload

Compose runs the production artifact — gunicorn, static files baked in. For
front-end work you want the Vite dev server instead:

```bash
cd backend && python manage.py runserver     # needs a local venv
cd frontend && npm install && npm run dev    # :5173
```

Django falls back to the dev server automatically when no build exists, so the
two halves find each other with no proxy configuration.

## How it fits together

**One image, two builds.** Vite compiles into `backend/portfolio/static/app/`,
which is gitignored — the Dockerfile builds it in a Node stage and copies only
the output into the Python stage. `collectstatic` runs at build time and
WhiteNoise serves the result, so there is no nginx container.

**Content is translated per row, not per template.** Chrome copy (nav, section
headings) ships in the React bundle because it never changes without a deploy.
Everything the CMS owns — titles, bodies, tag names, captions — lives in a
`Translation` row beside the original and arrives already in the right language.
Adding a language is a key set in `src/i18n.jsx` plus `CONTENT_LANGUAGES`; no
migration, because translations are rows.

Every endpoint answers in one language, resolved first-match-wins:

```
?lang=es  →  X-Language: es  →  Accept-Language  →  PORTFOLIO_DEFAULT_LANG
```

The choice comes back in the payload and as `Content-Language`, and every
response carries `Vary: Accept-Language, X-Language` so a cache in front keys
on it.

**Markdown places its own blocks.** Assets and metric tables each carry a short
`ref`. Drop `[[asset:9f2a1c07]]` or `[[metrics:before-after]]` on its own line
and that block renders *there*; anything never referenced still renders, appended
after the body. So a shortcode *moves* a block rather than opting it in, and a
typo is visible rather than silent.

**Numbers are two objects.** A `Metric` is one figure. A `MetricGroup` gathers
metrics through a many-to-many and decides how they look — `facts` (the four-up
bar), `impact` (the accented callout), or `table` (a comparison, showing only the
columns its metrics fill in). Because the group is the unit, a project can carry
a latency table and a cost table, and the same metric can appear in both without
being typed twice.

**Two axes ride on `<html>`.** `data-theme` is the design direction (`a`/`b`/`c`,
from `PORTFOLIO_THEME`); `data-mode` is the visitor's dark/light choice. A
pre-paint script resolves the mode, so a light visitor never sees a dark flash.

**Media goes to S3 when configured.** Leave `AWS_STORAGE_BUCKET_NAME` unset and
uploads stay in `backend/media/`. Set it and `portfolio/storages.py` takes over:
files land in the bucket and every URL is a short-lived presigned GET, so the
bucket needs no public-read policy. Signatures are cached just under their own
lifetime, so a page render reuses one rather than minting a signature per
request. In production no keys are set at all — boto3 falls through to the
instance role.

## API

| Endpoint | Returns |
|---|---|
| `GET /api/profile/` | hero, quote, bio, capability cards, closing line, contact |
| `GET /api/projects/` | list; `?domain=&tag=&year=&q=&featured=1` all compose |
| `GET /api/projects/<slug>/` | detail: rendered body, contents, metric tables, assets, prev/next |
| `GET /api/filters/` | domains, tags and years with counts |
| `GET /api/languages/` | what the site can be read in, and what this request resolved to |

## Deploying

Push to main. CI builds an arm64 image, pushes it to ECR, and a timer on the
instance notices the new digest within a couple of minutes.

The target is one t4g.micro with no public IPv4 and no inbound rule: it reaches
AWS over IPv6, and Cloudflare reaches it through a tunnel that dials out.

## Notes

- **Fonts** are system stacks. To self-host, add an `@font-face` block to
  `dataflow.css` and put the family first in `--df-font-display` / `--df-font-text`.
- **Motion** respects `prefers-reduced-motion` everywhere: the hero canvas never
  starts, counters jump to their final value.
- **Content is never hidden behind JavaScript** — scroll reveals arm themselves
  only once `<html class="js">` is set.
- **Preferences** (mode, language, view) live in `localStorage` under `df-`, with
  every read and write wrapped: some privacy modes throw rather than return null.
