#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# SYNAPSE — Celery Worker Startup Script
#
# Starts the background task worker that processes:
#   • Article NLP (clean, keyword extract, topic classify, sentiment, NER)
#   • Article summarization (Gemini 1.5 Flash)
#   • Vector embedding generation (sentence-transformers)
#   • Scraping tasks (HackerNews, GitHub, arXiv, YouTube)
#
# Usage:
#   chmod +x scripts/start_worker.sh
#   ./scripts/start_worker.sh
#
# Or run individual queues manually — see comments at the bottom.
# ─────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

# Load .env so GOOGLE_API_KEY and broker settings are available
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env"
  set +a
  echo "✅ Loaded .env"
fi

# Make sure ai_engine is on PYTHONPATH so Celery tasks can import it
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.development}"

echo ""
echo "🚀 Starting SYNAPSE Celery worker..."
echo "   DJANGO_SETTINGS_MODULE = $DJANGO_SETTINGS_MODULE"
echo "   PYTHONPATH includes     = $PROJECT_ROOT"
echo "   Queues                  = default, scraping, agents, nlp, embeddings"
echo ""

cd "$BACKEND_DIR"

# Ensure PYTHONPATH includes both backend/ (for Django) and project root (for scraper package)
PROJECT_ROOT="$(dirname "$BACKEND_DIR")"
export PYTHONPATH="$BACKEND_DIR:$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

# 4-worker setup — each queue pool is isolated so slow tasks never block fast ones:
#
# Worker 1 — default + agents: automation workflows, excerpt fetching, agent tasks
celery -A config.celery worker \
  --loglevel=info --concurrency=4 \
  --queues=default,agents \
  --hostname=synapse-default@%h \
  -P prefork &

# Worker 2 — scraping: fast scrapers (github, hackernews) — ~30s each
celery -A config.celery worker \
  --loglevel=info --concurrency=4 \
  --queues=scraping \
  --hostname=synapse-scraping@%h \
  -P prefork &

# Worker 3 — slow_scraping: arxiv (~10min) and youtube (~5min) — isolated
celery -A config.celery worker \
  --loglevel=info --concurrency=2 \
  --queues=slow_scraping \
  --hostname=synapse-slow@%h \
  -P prefork &

# Worker 4 — nlp + embeddings: NLP processing and vector embeddings (ML-heavy)
celery -A config.celery worker \
  --loglevel=info --concurrency=2 \
  --queues=nlp,embeddings \
  --hostname=synapse-nlp@%h \
  -P prefork &

wait

# ─────────────────────────────────────────────────────────────────────────────
# Alternative: run dedicated workers per queue in separate terminals
# for maximum throughput and isolation:
#
#   Terminal 1 — Workflow engine + automation (REQUIRED for ▶ Run button):
#   cd backend && celery -A config.celery worker -Q default --concurrency=2 --loglevel=info
#
#   Terminal 2 — Scraping tasks (HackerNews, GitHub, arXiv, YouTube):
#   cd backend && celery -A config.celery worker -Q scraping --concurrency=4 --loglevel=info
#
#   Terminal 3 — NLP + summarization (CPU-bound, ML models):
#   cd backend && celery -A config.celery worker -Q nlp --concurrency=1 --loglevel=info
#
#   Terminal 4 — Embedding generation:
#   cd backend && celery -A config.celery worker -Q embeddings --concurrency=1 --loglevel=info
#
#   Terminal 5 — Agent tasks:
#   cd backend && celery -A config.celery worker -Q agents --concurrency=2 --loglevel=info
#
#   Optional — Celery Beat (periodic task scheduler):
#   cd backend && celery -A config.celery beat --loglevel=info
# ─────────────────────────────────────────────────────────────────────────────
