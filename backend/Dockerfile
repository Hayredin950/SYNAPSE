# ── Stage 1: Dependencies (cached unless requirements.txt changes) ────────────
# Build context is the REPO ROOT (Render sends entire repo as context).
# So paths like backend/requirements.txt and scraper/ are available.
FROM python:3.11-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Copy ONLY backend requirements first — Docker caches this layer
COPY backend/requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt --use-deprecated=legacy-resolver

# ── Stage 2: Development ──────────────────────────────────────────────────────
FROM python:3.11-slim AS development
WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

RUN pip install yt-dlp --no-cache-dir

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Copy backend source code (not the whole repo)
COPY --chown=appuser:appuser backend/ .

# Copy ai_engine module (required for AI agents)
COPY --chown=appuser:appuser ai_engine/ ./ai_engine/

USER appuser
EXPOSE 8000

# ── Stage 3: Production ───────────────────────────────────────────────────────
FROM python:3.11-slim AS production
WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# yt-dlp is required by the YouTube scraper (scrape_videos workflow)
# beautifulsoup4 is required by the direct HTTP tweet scraper
RUN pip install yt-dlp beautifulsoup4 --no-cache-dir

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Copy backend source code (manage.py, config/, apps/ etc. go to /app/)
COPY --chown=appuser:appuser backend/ .

# Copy ai_engine module (required for AI agents, embeddings, NLP)
COPY --chown=appuser:appuser ai_engine/ ./ai_engine/

# Make the start scripts executable. We split the previous mega-CMD across
# three dedicated services on Render so the free-tier 512 MB cap isn't
# exceeded by running web + worker + beat in one container.
RUN chmod +x /app/start-web.sh /app/start-worker.sh /app/start-beat.sh /app/start-worker-with-health.sh

USER appuser
EXPOSE 8000

# Ensure production settings are used (asgi.py defaults to development)
ENV DJANGO_SETTINGS_MODULE=config.settings.production

# Default CMD = web service. The Celery worker and Beat services on Render
# override this via their "Docker Command" field with /app/start-worker.sh
# and /app/start-beat.sh respectively.
CMD ["/app/start-web.sh"]
