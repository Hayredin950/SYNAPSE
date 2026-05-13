#!/bin/bash

export DJANGO_SETTINGS_MODULE=config.settings.replit
export PYTHONPATH=/home/runner/workspace/synapse/backend:/home/runner/workspace/synapse
export DB_NAME=heliumdb
export DB_USER=postgres
export DB_PASSWORD=password
export DB_HOST=helium
export DB_PORT=5432

# ── Replit built-in AI integration — wire into summarizer + agent ─────────────
# These are set automatically by Replit; we re-export them under the names
# that the summarizer and LLM factory look for so no external API key is needed.
export OPENROUTER_API_KEY="${AI_INTEGRATIONS_OPENAI_API_KEY:-_DUMMY_API_KEY_}"
export OPENROUTER_BASE_URL="${AI_INTEGRATIONS_OPENAI_BASE_URL:-http://localhost:1106/modelfarm/openai}"
export OPENROUTER_MODEL="gpt-4o-mini"

# Disable all per-view rate limiting in the Replit environment.
# PlanAwareThrottle.allow_request() checks this and returns True unconditionally.
export DISABLE_RATE_LIMITS=true

# Robustly free port 8000 — kill all processes, then wait until the port is actually free
echo "Freeing port 8000..."
fuser -k 8000/tcp 2>/dev/null || true
for i in $(seq 1 10); do
  fuser 8000/tcp 2>/dev/null || break
  sleep 1
done

# ── Start Redis server (fast in-process cache + channel layer) ────────────────
echo "Starting Redis..."
fuser -k 6379/tcp 2>/dev/null || true
# Use known path first (avoids slow `find /nix/store`); fall back to PATH lookup
REDIS_BIN="/nix/store/9f8mvs1gssxandjg0azwjw8jlwzrmcis-redis-6.2.5/bin/redis-server"
if [ ! -x "$REDIS_BIN" ]; then
  REDIS_BIN=$(which redis-server 2>/dev/null || echo "")
fi
if [ -n "$REDIS_BIN" ] && [ -x "$REDIS_BIN" ]; then
  "$REDIS_BIN" --daemonize yes \
    --logfile /tmp/redis.log \
    --port 6379 \
    --maxmemory 64mb \
    --maxmemory-policy allkeys-lru \
    --save "" 2>/dev/null && echo "✓ Redis started" || echo "⚠ Redis failed to start"
else
  echo "⚠ redis-server not found — using in-memory cache"
fi

cd /home/runner/workspace/synapse/backend

echo "Installing required Python packages..."
pip install langchain-openai==0.2.14 "langgraph>=0.2.0,<0.3.0" yt-dlp django-redis redis --user --quiet 2>/dev/null || true

echo "Running database migrations..."
python manage.py migrate --noinput 2>&1 | tail -5 || true

echo "Collecting static files..."
python manage.py collectstatic --noinput -v 0 2>&1 | tail -3 || true

# ── Background scraper scheduler ─────────────────────────────────────────────
# Runs HackerNews (every 30min), GitHub (every 2hrs), arXiv (every 6hrs)
# in a background process. No Redis or Celery Beat required.
echo "Starting background scraper scheduler..."
python /home/runner/workspace/synapse/scraper_scheduler.py &> /tmp/scraper_scheduler.log &
echo "Scraper scheduler PID: $!"

echo "Starting Django backend on port 8000..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
