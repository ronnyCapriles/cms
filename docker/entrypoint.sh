#!/bin/sh
# On boot: set the journal mode, migrate, then serve.
set -e

python - <<'PY'
import os, pathlib, sqlite3

db = pathlib.Path(os.environ.get("DJANGO_DB_PATH", "/app/data/db.sqlite3"))
db.parent.mkdir(parents=True, exist_ok=True)

# WAL lets workers read while one writes. The default rollback journal locks the
# whole file, turning an admin save into "database is locked" for every reader.
# It is a property of the file, so this only has to land once.
with sqlite3.connect(db) as conn:
    conn.execute("PRAGMA journal_mode=WAL")
PY

# The last moment the schema is guaranteed current before a worker forks.
python manage.py migrate --noinput

exec gunicorn config.wsgi:application \
  --bind "${GUNICORN_BIND:-0.0.0.0:8000}" \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
