#!/bin/sh
# ── synapse-celery-beat Background Worker start script (OPTIONAL) ────────────
# Only needed if you use scheduled (cron-style) automation workflows. Manual
# "Run" triggers from the Automation UI work without Beat thanks to the
# sync-fallback in apps/automation/views.py.
set -e

echo "[start-beat] starting celery beat..."
exec celery -A config.celery beat \
  -l info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler \
  --pidfile=/tmp/celerybeat.pid
