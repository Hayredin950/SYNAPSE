#!/bin/bash

export PORT=22167
export NEXT_PUBLIC_API_URL=
export NEXT_PUBLIC_WS_URL=
export NEXT_PUBLIC_APP_URL=
export NEXT_PUBLIC_APP_NAME=SYNAPSE
export NEXT_TELEMETRY_DISABLED=1

NEXT_BIN="node /home/runner/workspace/synapse/frontend/node_modules/next/dist/bin/next"

echo "Freeing port $PORT..."
fuser -k ${PORT}/tcp 2>/dev/null || true
for i in $(seq 1 8); do
  fuser ${PORT}/tcp 2>/dev/null || break
  sleep 1
done

cd /home/runner/workspace/synapse/frontend

# Always run in dev mode — avoids build timeout and .next/ conflicts.
# Next.js dev mode (with Turbopack) is fast, fully functional, and port-ready in <5s.
echo "Starting SYNAPSE in dev mode on port $PORT (Turbopack)..."
export NODE_ENV=development
exec $NEXT_BIN dev --turbopack --port $PORT --hostname 0.0.0.0
