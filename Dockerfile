# syntax=docker/dockerfile:1.7
#
# Two stages: Vite's output is gitignored, so the image builds the bundle rather
# than copying it in. Node stays behind in stage 1; the shipped image is Python
# plus the compiled assets.
#
# Built for linux/arm64 — the target is a t4g.micro (Graviton).

# ---- stage 1: the React bundle ----
FROM node:22-alpine AS frontend

WORKDIR /build

# Manifests first, so editing a component does not reinstall node_modules.
# No --mount=type=cache: npm hardlinks out of it and esbuild's postinstall then
# execs a binary it still holds open (ETXTBSY). The layer cache suffices here.
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN npm --prefix frontend ci

# index.css imports ../../../design-system/dataflow.css, so the token layer has
# to be in the build context too.
COPY design-system/ ./design-system/
COPY frontend/ ./frontend/

# vite.config.js writes to ../backend/portfolio/static/app, relative to the
# frontend dir — i.e. /build/backend/portfolio/static/app.
RUN npm --prefix frontend run build

# ---- stage 2: Django ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    DJANGO_DB_PATH=/app/data/db.sqlite3

WORKDIR /app

# Pillow ships prebuilt aarch64 wheels, so only its runtime libraries are needed.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
COPY --from=frontend /build/backend/portfolio/static/app/ ./portfolio/static/app/

# Baked in, so a booting container never writes static files or races another
# worker doing the same. The key is a throwaway: collectstatic signs nothing.
RUN DJANGO_SECRET_KEY=build-time-only DJANGO_DEBUG=0 \
    python manage.py collectstatic --noinput

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# /app/data is where the EBS volume mounts. Created here so it inherits the
# app user's ownership rather than root's.
RUN useradd --system --uid 10001 --create-home --home-dir /home/app app \
 && mkdir -p /app/data /app/media \
 && chown -R app:app /app
USER app

EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
