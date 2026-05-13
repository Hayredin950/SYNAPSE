#!/bin/bash
set -e

export DJANGO_SETTINGS_MODULE=config.settings.replit
export PYTHONPATH=/home/runner/workspace/synapse/backend:/home/runner/workspace/synapse

# Use Replit's PostgreSQL env vars
export DB_NAME="${PGDATABASE:-heliumdb}"
export DB_USER="${PGUSER:-postgres}"
export DB_PASSWORD="${PGPASSWORD:-password}"
export DB_HOST="${PGHOST:-helium}"
export DB_PORT="${PGPORT:-5432}"

# Replit AI integration
export OPENROUTER_API_KEY="${AI_INTEGRATIONS_OPENAI_API_KEY:-_DUMMY_API_KEY_}"
export OPENROUTER_BASE_URL="${AI_INTEGRATIONS_OPENAI_BASE_URL:-http://localhost:1106/modelfarm/openai}"
export OPENROUTER_MODEL="gpt-4o-mini"

# Used by Django settings for AI
export OPENAI_API_KEY="${AI_INTEGRATIONS_OPENAI_API_KEY:-_DUMMY_API_KEY_}"
export OPENAI_API_BASE="${AI_INTEGRATIONS_OPENAI_BASE_URL:-http://localhost:1106/modelfarm/openai}"

export DISABLE_RATE_LIMITS=true
export SECRET_KEY="synapse-replit-dev-secret-key-change-in-production-xyz123"
export DEBUG=True
export ALLOWED_HOSTS="*"

echo "=== SYNAPSE Backend ==="
echo "DB: $DB_HOST/$DB_NAME"
echo "Python: $(python3 --version)"

# Free port 8000
echo "Freeing port 8000..."
fuser -k 8000/tcp 2>/dev/null || true
sleep 1

# Start Redis if available
echo "Starting Redis..."
fuser -k 6379/tcp 2>/dev/null || true
REDIS_BIN=$(which redis-server 2>/dev/null || echo "")
if [ -n "$REDIS_BIN" ]; then
  "$REDIS_BIN" --daemonize yes \
    --logfile /tmp/redis.log \
    --port 6379 \
    --maxmemory 64mb \
    --maxmemory-policy allkeys-lru \
    --save "" 2>/dev/null && echo "✓ Redis started" || echo "⚠ Redis not started"
else
  echo "⚠ No redis-server — using in-memory cache"
fi

cd /home/runner/workspace/synapse/backend

echo "Running database migrations..."
python3 manage.py migrate --noinput 2>&1 | tail -10 || true

echo "Collecting static files..."
python3 manage.py collectstatic --noinput -v 0 2>&1 | tail -3 || true

echo "Starting scraper scheduler in background..."
python3 /home/runner/workspace/synapse/scraper_scheduler.py &>/tmp/scraper.log &
echo "Scheduler PID: $!"

echo "Starting Django on port 8000..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
