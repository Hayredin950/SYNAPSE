#!/bin/sh
# ── synapse-celery-worker Background Worker start script ─────────────────────
# Runs the Celery worker only (no Beat). Concurrency and the per-child task
# cap are env-driven so we can tune them without rebuilding the image when
# moving between hosts:
#   * Render free  (512 MB) → CELERY_CONCURRENCY=2  CELERY_MAX_TASKS_PER_CHILD=50
#   * Koyeb Nano   (256 MB) → CELERY_CONCURRENCY=1  CELERY_MAX_TASKS_PER_CHILD=20
#   * Anything paid (≥1 GB) → CELERY_CONCURRENCY=4+ CELERY_MAX_TASKS_PER_CHILD=100
# Defaults below match the smallest realistic environment so we never OOM on
# first boot, then operators bump them up via env vars when they have RAM.
set -e

CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-1}"
CELERY_MAX_TASKS_PER_CHILD="${CELERY_MAX_TASKS_PER_CHILD:-20}"
CELERY_QUEUES="${CELERY_QUEUES:-default,scraping,slow_scraping,agents,nlp,embeddings}"
CELERY_LOGLEVEL="${CELERY_LOGLEVEL:-info}"

(
  echo "[start-worker] concurrency=${CELERY_CONCURRENCY} max-tasks-per-child=${CELERY_MAX_TASKS_PER_CHILD} queues=${CELERY_QUEUES}"
  echo "[start-worker] CELERY_BROKER_URL=${CELERY_BROKER_URL:-(not set)}"
  echo "[start-worker] DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-(not set)}"

  # Test that Django settings can be loaded
  echo "[start-worker] Testing Django setup..."
  python -c "import django; django.setup(); print('[start-worker] Django settings loaded successfully')" || {
    echo "[start-worker] ERROR: Failed to load Django settings"
    exit 1
  }

  # Test that Celery app can be imported
  echo "[start-worker] Testing Celery app import..."
  python -c "from config.celery import app; print('[start-worker] Celery app imported successfully')" || {
    echo "[start-worker] ERROR: Failed to import Celery app from config.celery"
    exit 1
  }

  echo "[start-worker] All pre-checks passed. Starting Celery worker..."
) >&2

exec celery -A config.celery worker \
  -Q "${CELERY_QUEUES}" \
  -c "${CELERY_CONCURRENCY}" \
  -l "${CELERY_LOGLEVEL}" \
  --max-tasks-per-child="${CELERY_MAX_TASKS_PER_CHILD}"


