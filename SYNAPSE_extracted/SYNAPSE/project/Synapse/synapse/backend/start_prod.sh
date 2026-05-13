#!/bin/bash
# ── SYNAPSE Production Start Script ──────────────────────────────────────────
# Runs BOTH the web server AND Celery worker+beat in a single container.
# This is the free-tier deployment strategy (no separate background worker).
# ─────────────────────────────────────────────────────────────────────────────

set -e

echo "🚀 SYNAPSE Production Start"
echo "──────────────────────────────"

# 1. Run migrations
echo "📦 Running migrations..."
python manage.py migrate --noinput 2>&1 || echo "⚠️  Migrations failed (may be OK on first deploy)"

# 2. Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear 2>/dev/null || python manage.py collectstatic --noinput 2>/dev/null || echo "⚠️  Static files skipped"

# 3. Start Celery worker + beat in background
echo "⚙️  Starting Celery worker + beat..."
celery -A config.celery worker -B \
  -Q default,scraping,agents,nlp,embeddings,slow_scraping \
  -c 4 -l info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler \
  --pidfile=/tmp/celerybeat.pid &

CELERY_PID=$!
echo "   Celery PID: $CELERY_PID"

# 4. Start Daphne ASGI server (foreground) — supports HTTP + WebSocket
# Gunicorn (WSGI) cannot handle WebSocket connections;
# Daphne is the official ASGI server for Django Channels.
echo "🌐 Starting Daphne ASGI server..."
exec daphne config.asgi:application \
  --bind 0.0.0.0 \
  --port "${PORT:-8000}" \
  --verbosity 1
