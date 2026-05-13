#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# SYNAPSE — Local Development Startup Script
# Starts: Django backend, FastAPI AI engine, Next.js frontend
# Prerequisites: Docker services already running (docker compose up -d)
# Usage: bash scripts/start_local.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "════════════════════════════════════════════════"
echo "         🚀 Starting SYNAPSE Local Dev Stack"
echo "════════════════════════════════════════════════"

# ── Load environment variables ────────────────────────────────────────────────
if [ -f .env ]; then
  export $(grep -v '^#' .env | grep -v '^$' | xargs) 2>/dev/null
  echo "✅ Environment loaded from .env"
else
  echo "⚠️  No .env file found! Copy .env.example → .env and fill in values."
  exit 1
fi

VENV="$PROJECT_ROOT/backend/venv"
if [ ! -d "$VENV" ]; then
  echo "❌ Python venv not found at $VENV"
  echo "   Run: cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# ── Check Docker services ─────────────────────────────────────────────────────
echo ""
echo "🐳 Checking Docker services..."
docker ps --format "  {{.Names}}: {{.Status}}" | grep synapse || {
  echo "  ⚠️  Docker services not running. Starting them..."
  docker compose up -d postgres redis celery_worker celery_beat flower
  sleep 5
}

# ── Kill any existing local processes ────────────────────────────────────────
echo ""
echo "🔄 Stopping any existing local processes..."
pkill -f "manage.py runserver" 2>/dev/null || true
pkill -f "uvicorn ai_engine" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
sleep 2

# ── Start Django Backend (port 8000) ─────────────────────────────────────────
echo ""
echo "🔵 Starting Django backend on http://localhost:8000 ..."
cd "$PROJECT_ROOT/backend"
source "$VENV/bin/activate"
DJANGO_SETTINGS_MODULE=config.settings.development \
PYTHONPATH="$PROJECT_ROOT/backend:$PROJECT_ROOT" \
python manage.py runserver 0.0.0.0:8000 --noreload \
  > /tmp/synapse_django.log 2>&1 &
DJANGO_PID=$!
echo "  PID: $DJANGO_PID → logs: /tmp/synapse_django.log"

# ── Start FastAPI AI Engine (port 8002) ──────────────────────────────────────
echo ""
echo "🤖 Starting FastAPI AI engine on http://localhost:8002 ..."
cd "$PROJECT_ROOT"
source "$VENV/bin/activate"
PYTHONPATH="$PROJECT_ROOT" \
uvicorn ai_engine.main:app --host 0.0.0.0 --port 8002 --reload \
  > /tmp/synapse_ai.log 2>&1 &
AI_PID=$!
echo "  PID: $AI_PID → logs: /tmp/synapse_ai.log"

# ── Start Next.js Frontend (port 3000) ───────────────────────────────────────
echo ""
echo "⚛️  Starting Next.js frontend on http://localhost:3000 ..."
cd "$PROJECT_ROOT/frontend"
npm run dev > /tmp/synapse_frontend.log 2>&1 &
FE_PID=$!
echo "  PID: $FE_PID → logs: /tmp/synapse_frontend.log"

# ── Wait for services to come up ─────────────────────────────────────────────
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 8

# ── Health checks ─────────────────────────────────────────────────────────────
echo ""
echo "════════ Health Checks ════════"
check() {
  local name=$1 url=$2
  if curl -sf "$url" > /dev/null 2>&1; then
    echo "  ✅ $name → $url"
  else
    echo "  ❌ $name not responding at $url (check logs)"
  fi
}

check "Django Backend"   "http://localhost:8000/api/v1/health/"
check "FastAPI AI Engine" "http://localhost:8002/health"
check "Next.js Frontend"  "http://localhost:3000"
check "Frontend Proxy"    "http://localhost:3000/api/v1/health/"
check "Celery Flower"     "http://localhost:5555"

echo ""
echo "════════════════════════════════════════════════"
echo "  🎉 SYNAPSE is running!"
echo ""
echo "  Frontend:    http://localhost:3000"
echo "  Backend API: http://localhost:8000/api/v1/"
echo "  AI Engine:   http://localhost:8002/docs"
echo "  Flower:      http://localhost:5555"
echo "  Admin:       http://localhost:8000/admin/"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "════════════════════════════════════════════════"

# ── Trap Ctrl+C to clean up ───────────────────────────────────────────────────
cleanup() {
  echo ""
  echo "Stopping services..."
  kill $DJANGO_PID $AI_PID $FE_PID 2>/dev/null
  echo "All local services stopped."
}
trap cleanup INT TERM

wait
