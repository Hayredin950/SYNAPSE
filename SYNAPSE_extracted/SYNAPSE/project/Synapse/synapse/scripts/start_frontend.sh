#!/usr/bin/env bash
# ── SYNAPSE Frontend Dev Server ──────────────────────────────────────────────
# Clears stale .next cache and starts Next.js dev server fresh.
# Usage: bash scripts/start_frontend.sh

set -e
FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"

echo "🧹 Clearing stale .next cache..."
rm -rf "$FRONTEND_DIR/.next" 2>/dev/null || true

echo "🚀 Starting Next.js dev server on http://localhost:3000"
cd "$FRONTEND_DIR"
NEXT_TELEMETRY_DISABLED=1 \
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 \
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws \
npx next dev -p 3000
