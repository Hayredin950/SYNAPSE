#!/bin/bash

export PORT=3000
export NEXT_PUBLIC_API_URL=""
export NEXT_PUBLIC_WS_URL=""
export NEXT_PUBLIC_APP_URL=""
export NEXT_PUBLIC_APP_NAME=SYNAPSE
export NEXT_TELEMETRY_DISABLED=1
export NODE_ENV=development

echo "=== SYNAPSE Frontend ==="
echo "Node: $(node --version)"

# Free port
echo "Freeing port $PORT..."
fuser -k ${PORT}/tcp 2>/dev/null || true
sleep 1

cd /home/runner/workspace/synapse/frontend

# Install deps if node_modules missing
if [ ! -d "node_modules/next" ]; then
  echo "Installing frontend dependencies..."
  npm install --legacy-peer-deps 2>&1 | tail -5
fi

echo "Starting Next.js on port $PORT..."
exec node node_modules/next/dist/bin/next dev --port $PORT --hostname 0.0.0.0
