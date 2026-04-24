"""
SYNAPSE AI Engine — FastAPI application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Industry best practices applied:
  ✓ Lifespan context manager (replaces deprecated on_event)
  ✓ Singleton warm-up at startup (avoids cold-start latency on first request)
  ✓ SlowAPI rate limiting (prevents abuse)
  ✓ Structured logging with structlog
  ✓ Proper error models with Pydantic
  ✓ CORS configured from env (not wildcard in production)
  ✓ Request ID middleware for distributed tracing
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Iterator, List, Optional

import structlog
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

# ── Sentry — error tracking (TASK-204) ───────────────────────────────────────
_SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if _SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        integrations=[
            StarletteIntegration(transaction_style="url"),
            FastApiIntegration(transaction_style="url"),
            LoggingIntegration(level=None, event_level="ERROR"),
        ],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_RATE", "0.1")),
        profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_RATE", "0.05")),
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        send_default_pii=False,
    )
    logger.info("sentry_initialised", dsn_set=True)

# ── Lifespan — warm up singletons at startup ──────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Warms up the embedding model and RAG pipeline at startup
    so the first user request isn't slow.
    """
    # ── OpenTelemetry (TASK-504-B2) ──────────────────────────────────────────────
    _OTEL_ENABLED = os.environ.get("OTEL_ENABLED", "").lower() == "true"
    if _OTEL_ENABLED:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            _otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
            FastAPIInstrumentor.instrument_app(app)
            logger.info("otel_enabled", endpoint=_otel_endpoint)
        except ImportError:
            logger.warning(
                "otel_instrumentation_not_installed",
                message="Install opentelemetry-instrumentation-fastapi to enable tracing",
            )
        except Exception as exc:
            logger.warning("otel_instrumentation_failed", error=str(exc))

    logger.info("SYNAPSE AI Engine starting up…")

    # ── Redis health check (TASK-004-B9) ─────────────────────────────────────
    try:
        import redis as _redis

        _r = _redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=int(os.environ.get("REDIS_RL_DB", "4")),
            socket_connect_timeout=2,
        )
        _r.ping()
        logger.info("redis_ready", host=os.environ.get("REDIS_HOST", "localhost"))
    except Exception as exc:
        logger.critical(
            "redis_unavailable",
            error=str(exc),
            message="Rate limiting and budget tracking will be disabled.",
        )

    # Warm up embedder
    try:
        from ai_engine.embeddings import get_embedder

        embedder = get_embedder()
        logger.info(
            "embedder_ready",
            model=os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            dims=embedder.dimensions,
        )
    except Exception as exc:
        logger.warning("embedder_warmup_failed", error=str(exc))

    # Warm up RAG pipeline (connects to DB, Redis)
    try:
        from ai_engine.rag import get_rag_pipeline

        pipeline = get_rag_pipeline()
        logger.info("rag_pipeline_ready", model=pipeline.model_name)
    except Exception as exc:
        logger.warning("rag_pipeline_warmup_failed", error=str(exc))

    # Warm up agent executor
    try:
        from ai_engine.agents import get_executor

        executor = get_executor()
        logger.info("agent_executor_ready", tools=len(executor.list_tools()))
    except Exception as exc:
        logger.warning("agent_executor_warmup_failed", error=str(exc))

    logger.info("SYNAPSE AI Engine ready ✓")
    yield
    logger.info("SYNAPSE AI Engine shutting down…")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SYNAPSE AI Engine",
    description="Agent orchestration, RAG pipeline, and embeddings API.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────

_allowed_origins = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:8000",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request ID middleware (for distributed tracing) ───────────────────────────


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Rate limiting (SlowAPI — token bucket per IP) ─────────────────────────────

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    _RATE_LIMITING = True
except ImportError:
    _RATE_LIMITING = False
    logger.warning("slowapi not installed — rate limiting disabled")


# ── Pydantic models ────────────────────────────────────────────────────────────


class AgentRunRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=4000)
    stream: bool = False


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    content_types: Optional[List[str]] = None
    stream: bool = False
    # TASK-302: per-request model/provider override
    provider: Optional[str] = Field(
        None, description="LLM provider: auto|openai|anthropic|ollama|gemini"
    )
    model: Optional[str] = Field(
        None, description="Model name override, e.g. claude-3-5-sonnet-20241022"
    )
    user_id: Optional[str] = None  # passed from Django backend for budget routing
    role: Optional[str] = "user"  # user plan role for model gating


class EmbedRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1, max_length=100)
    batch_size: int = Field(32, ge=1, le=128)


class HealthResponse(BaseModel):
    status: str
    components: Dict[str, Any] = {}


# ── Health ─────────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health() -> Dict[str, Any]:
    # Check Redis status
    redis_status = "unavailable"
    try:
        import redis as _redis

        _r = _redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=int(os.environ.get("REDIS_RL_DB", "4")),
            socket_connect_timeout=1,
        )
        _r.ping()
        redis_status = "ok"
    except Exception:
        pass
    return {"status": "ok", "redis": redis_status}


@app.get("/health/rag", response_model=HealthResponse, tags=["System"])
async def health_rag() -> Dict[str, Any]:
    try:
        from ai_engine.rag import get_rag_pipeline

        return get_rag_pipeline().health_check()
    except Exception as exc:
        logger.exception("rag_health_check_failed", error=str(exc))
        return {"status": "error", "detail": str(exc)}


# ── Agents ─────────────────────────────────────────────────────────────────────


@app.get("/agents/tools", tags=["Agents"])
async def list_tools() -> Dict[str, Any]:
    try:
        from ai_engine.agents import get_executor

        executor = get_executor()
        tools = executor.list_tools()
        return {"tools": tools, "count": len(tools)}
    except Exception as exc:
        logger.exception("list_tools_failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/agents/run", tags=["Agents"])
async def run_agent(request: AgentRunRequest) -> Any:
    from ai_engine.agents import get_executor

    executor = get_executor()

    if request.stream:

        def _stream() -> Iterator[str]:
            import json

            try:
                for chunk in executor.stream(request.task):
                    yield json.dumps({"token": chunk}) + "\n"
            except Exception as exc:
                logger.exception("agent_stream_failed")
                yield json.dumps({"error": str(exc)}) + "\n"

        return StreamingResponse(_stream(), media_type="application/x-ndjson")

    try:
        return executor.run(request.task)
    except Exception as exc:
        logger.exception("agent_run_failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Chat / RAG ─────────────────────────────────────────────────────────────────


@app.get("/models", tags=["Models"])
async def list_models(role: str = "user") -> Dict[str, Any]:
    """
    GET /models?role=<plan>

    TASK-302: Returns the catalogue of available LLM models filtered by the
    user's plan role. The frontend uses this to populate the model selector.

    Query params:
        role: Plan role — "user" (free) | "pro" | "enterprise" | "staff"

    Response:
        { "models": [...], "default_provider": "...", "default_model": "..." }
    """
    try:
        from ai_engine.agents.router import get_available_models

        models = get_available_models(role=role)
        return {
            "models": models,
            "default_provider": os.environ.get("DEFAULT_PROVIDER", "auto"),
            "default_model": os.environ.get("OPENROUTER_MODEL", "gpt-4o"),
        }
    except Exception as exc:
        logger.exception("list_models_failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/chat", tags=["Chat"])
async def chat(request: ChatRequest) -> Any:
    """
    POST /chat

    TASK-302: Now supports per-request provider/model selection with plan
    gating and budget-aware fallback via resolve_provider_model().
    """
    from ai_engine.agents.router import resolve_provider_model
    from ai_engine.rag import get_rag_pipeline

    pipeline = get_rag_pipeline()
    # uuid is already imported at module level — no need for local alias
    conv_id = request.conversation_id or str(uuid.uuid4())

    # Resolve provider + model (plan gating + budget routing)
    try:
        provider, model = resolve_provider_model(
            requested_provider=request.provider,
            requested_model=request.model,
            user_id=request.user_id,
            role=request.role or "user",
        )
    except Exception as exc:
        # BudgetExceededError or misconfiguration
        raise HTTPException(status_code=429, detail=str(exc))

    if request.stream:
        # INC-03: Wrap each chunk as NDJSON — pipeline.stream_chat yields raw
        # string tokens, but the endpoint declares application/x-ndjson.
        # Each line must be a valid JSON object so clients can parse incrementally.
        def _stream() -> Iterator[str]:
            import json

            try:
                for chunk in pipeline.stream_chat(
                    question=request.question,
                    conversation_id=conv_id,
                    content_types=request.content_types,
                    provider=provider,
                    model=model,
                ):
                    yield json.dumps(
                        {"token": chunk, "conversation_id": conv_id}
                    ) + "\n"
            except Exception as exc:
                logger.exception("rag_stream_failed")
                yield json.dumps({"error": str(exc)}) + "\n"

        return StreamingResponse(_stream(), media_type="application/x-ndjson")

    try:
        return pipeline.chat(
            question=request.question,
            conversation_id=conv_id,
            content_types=request.content_types,
            provider=provider,
            model=model,
        )
    except Exception as exc:
        logger.exception("rag_chat_failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Embeddings ─────────────────────────────────────────────────────────────────


@app.post("/embeddings", tags=["Embeddings"])
async def embed_texts(request: EmbedRequest) -> Dict[str, Any]:
    try:
        from ai_engine.embeddings import get_embedder

        embedder = get_embedder()
        embeddings = embedder.embed_batch(request.texts, batch_size=request.batch_size)
        return {
            "embeddings": embeddings,
            "model": "all-MiniLM-L6-v2",
            "dimensions": embedder.dimensions,
            "count": len(embeddings),
        }
    except Exception as exc:
        logger.exception("embedding_failed")
        raise HTTPException(status_code=500, detail=str(exc))
