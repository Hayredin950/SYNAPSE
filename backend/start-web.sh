#!/bin/sh
# ── synapse-api WEB service start script ─────────────────────────────────────
# Runs migrations + collectstatic, then starts Daphne. NO Celery here — that
# lives in the dedicated synapse-celery-worker Background Worker on Render so
# the web service stays under Render free-tier's 512 MB memory cap.
set -e

echo "[start-web] running migrations..."
python manage.py migrate --noinput

echo "[start-web] collecting static files..."
python manage.py collectstatic --noinput --clear || true

echo "[start-web] starting daphne on port ${PORT:-8000}..."
exec daphne config.asgi:application \
  --bind 0.0.0.0 \
  --port "${PORT:-8000}" \
  --verbosity 1
