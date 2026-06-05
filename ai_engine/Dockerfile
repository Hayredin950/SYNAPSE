FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY ai_engine/requirements.txt .
# Install CPU-only torch first (avoids 5GB+ NVIDIA CUDA libraries)
RUN pip install --upgrade pip \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt --use-deprecated=legacy-resolver

FROM python:3.11-slim AS production
WORKDIR /app
RUN apt-get update && apt-get install -y libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Copy entire project so ai_engine package is importable as /app/ai_engine
COPY --chown=appuser:appuser . .
ENV PYTHONPATH=/app
USER appuser
EXPOSE 8001
CMD ["uvicorn", "ai_engine.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
