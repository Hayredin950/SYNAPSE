#!/bin/bash

export DJANGO_SETTINGS_MODULE=config.settings.replit
export PYTHONPATH=/home/runner/workspace/synapse/backend:/home/runner/workspace/synapse
export DB_NAME=heliumdb
export DB_USER=postgres
export DB_PASSWORD=password
export DB_HOST=helium
export DB_PORT=5432

# ── Replit built-in AI integration — wire into summarizer + agent ─────────────
export OPENROUTER_API_KEY="${AI_INTEGRATIONS_OPENAI_API_KEY:-_DUMMY_API_KEY_}"
export OPENROUTER_BASE_URL="${AI_INTEGRATIONS_OPENAI_BASE_URL:-http://localhost:1106/modelfarm/openai}"
export OPENROUTER_MODEL="gpt-4o-mini"

# Disable all per-view rate limiting in the Replit environment.
export DISABLE_RATE_LIMITS=true

# Robustly free port 8000
echo "Freeing port 8000..."
fuser -k 8000/tcp 2>/dev/null || true
for i in $(seq 1 10); do
  fuser 8000/tcp 2>/dev/null || break
  sleep 1
done

# ── Start Redis server ────────────────────────────────────────────────────────
echo "Starting Redis..."
fuser -k 6379/tcp 2>/dev/null || true
REDIS_BIN=$(which redis-server 2>/dev/null || echo "")
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

# ── Migrations — skip if already applied this session (saves ~90s per restart)
# The marker /tmp/synapse_migrated is created after a successful migrate run.
# It is cleared on container restart (new session) so migrations always run once.
if [ -f /tmp/synapse_migrated ]; then
  echo "Skipping migrations — already applied this session."
else
  echo "Running database migrations..."
  python3 manage.py migrate --noinput 2>&1 | tail -5 || true
  touch /tmp/synapse_migrated
fi

# ── Static files — skip if already collected this session (saves ~90s per restart)
if [ -f /tmp/synapse_static ]; then
  echo "Skipping collectstatic — already collected this session."
else
  echo "Collecting static files..."
  python3 manage.py collectstatic --noinput -v 0 2>&1 | tail -3 || true
  touch /tmp/synapse_static
fi

# ── Seed content if DB is empty (articles/repos) ──────────────────────────────
echo "Checking if content seeding is needed..."
python3 /home/runner/workspace/synapse/seed_content.py &> /tmp/seed_content.log &
echo "Content seeder PID: $!"

# ── Background scraper scheduler ──────────────────────────────────────────────
echo "Starting background scraper scheduler..."
python3 /home/runner/workspace/synapse/scraper_scheduler.py &> /tmp/scraper_scheduler.log &
echo "Scraper scheduler PID: $!"

echo "Starting Django backend on port 8000..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
