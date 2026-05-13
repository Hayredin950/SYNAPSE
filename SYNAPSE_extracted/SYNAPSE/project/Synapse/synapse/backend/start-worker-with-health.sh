#!/bin/sh
# start-worker-with-health.sh: Celery worker + health check server
set -e

PORT="${PORT:-10000}"

# Start health server in background
python - <<'PY' &
import http.server, socketserver, os, sys

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, fmt, *args):
        pass

port = int(os.environ.get("PORT", "10000"))
with socketserver.TCPServer(("0.0.0.0", port), H) as s:
    s.allow_reuse_address = True
    sys.stderr.write(f"[health] listening on 0.0.0.0:{port}\n")
    sys.stderr.flush()
    s.serve_forever()
PY

HEALTH_PID=$!
echo "[start-worker-with-health] health server started (PID=$HEALTH_PID)"

# Kill health server when celery exits
trap 'echo "[start-worker-with-health] terminating health server PID=$HEALTH_PID"; kill -TERM "$HEALTH_PID" 2>/dev/null || true' EXIT INT TERM

echo "[start-worker-with-health] starting celery worker..."
exec /app/start-worker.sh

