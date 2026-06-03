"""
SYNAPSE Django Base Settings
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (one level above the backend/ directory)
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    # In production on Render, derive a stable key from the external hostname
    # so the app doesn't crash on missing env var. This is less secure than
    # a proper random secret but prevents 502 errors on misconfigured deploys.
    _render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
    if _render_host:
        import hashlib
        SECRET_KEY = hashlib.sha256(f"synapse-{_render_host}".encode()).hexdigest()[:50]
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "The SECRET_KEY environment variable is not set. "
            'Generate one with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" '
            "and add it to your .env file."
        )
# Default DEBUG to False — fail safe. Developers must explicitly set DEBUG=True.
DEBUG = os.environ.get("DEBUG", "False") == "True"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

# ── Applications ─────────────────────────────────────────────
DJANGO_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "axes",
    "django_celery_beat",
    "django_celery_results",
    # 'django_prometheus',  # Re-enable after upgrading: pip install django-prometheus>=2.3
]

LOCAL_APPS = [
    "apps.core",
    "apps.users",
    "apps.articles",
    "apps.repositories",
    "apps.papers",
    "apps.videos",
    "apps.tweets",  # X/Twitter integration
    "apps.automation",
    "apps.agents",
    "apps.documents",
    "apps.trends",
    "apps.notifications",
    "apps.integrations",  # Phase 6 — Cloud Integration (Google Drive + AWS S3)
    "apps.billing",  # Phase 9.3 — Stripe billing, referrals, feedback
    "apps.organizations",  # TASK-006 — Team Workspaces & Organizations
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── Middleware ────────────────────────────────────────────────
MIDDLEWARE = [
    "apps.core.rate_limit_middleware.RateLimitHeaderMiddleware",  # TASK-501-B4
    "apps.core.middleware.APIVersionHeaderMiddleware",  # TASK-105-4: X-API-Version header
    # 'django_prometheus.middleware.PrometheusBeforeMiddleware',
    "django.middleware.security.SecurityMiddleware",
    # Phase 9.1 — Security hardening (must run BEFORE CorsMiddleware to apply to OPTIONS preflight)
    "apps.core.security.SecurityHeadersMiddleware",
    "apps.core.security.ContentSecurityPolicyMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # 'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ── Database ─────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",  # works with psycopg2 or psycopg3
        "NAME": os.environ.get("DB_NAME", "synapse_db"),
        "USER": os.environ.get("DB_USER", "synapse_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "synapse_pass"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 600,  # Keep DB connections alive for 10 min — enables connection reuse under load
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}

# ── Cache (Redis) ─────────────────────────────────────────────
# ── Django Channels ───────────────────────────────────────────
ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL", "redis://localhost:6379/0")],
            "capacity": 1500,
            "expiry": 10,
        },
    },
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
        },
        "KEY_PREFIX": "synapse",
        "TIMEOUT": 3600,  # 1 hour default (was 300s — too aggressive for stable data)
    }
}

# CFG-06: Use cached_db session backend instead of pure cache.
# The pure 'cache' backend loses ALL sessions if Redis crashes or restarts,
# instantly logging out every user. 'cached_db' reads from Redis (fast path)
# and falls back to PostgreSQL (durable) — best of both worlds.
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"

# ── Auth ──────────────────────────────────────────────────────
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ── Email (SendGrid) ─────────────────────────────────────────
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",  # dev: prints to console
)
# For production with SendGrid SMTP:
#   EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
#   EMAIL_HOST    = 'smtp.sendgrid.net'
#   EMAIL_PORT    = 587
#   EMAIL_USE_TLS = True
#   EMAIL_HOST_USER = 'apikey'
#   EMAIL_HOST_PASSWORD = os.environ.get('SENDGRID_API_KEY')
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "apikey")
# Prefer EMAIL_HOST_PASSWORD (set in .env for Brevo/SMTP providers) and fall
# back to SENDGRID_API_KEY for backward-compat with legacy SendGrid deployments.
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD") or os.environ.get(
    "SENDGRID_API_KEY", ""
)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@synapse.ai")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")

# ── Firebase Auth (FREE email sending for verification & password reset) ──────
# Setup: https://console.firebase.google.com → Create project → Enable Auth
# Set these env vars:
#   FIREBASE_WEB_API_KEY               — from Project Settings > General
#   GOOGLE_APPLICATION_CREDENTIALS     — path to service account JSON
#   OR FIREBASE_CREDENTIALS_JSON       — service account JSON as string
FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY", "")

# ── REST Framework ────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "apps.core.auth.APIKeyAuthentication",  # TASK-605-B2
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # TASK-501: Plan-aware throttling — PlanAwareThrottle reads user plan from billing
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "apps.core.throttles.APIRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/minute",
        "user": "1000/minute",  # dashboard has multiple polling queries
        "mfa_verify": "5/minute",  # Strict: prevents TOTP brute force
        "mfa_setup": "3/minute",  # Strict: prevents setup abuse
        "login": "10/minute",  # Brute force protection on login
        "registration": "5/hour",  # Anti-spam on registration endpoint
    },
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
}

# ── JWT ───────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", 15))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_LIFETIME_DAYS", 7))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ── CORS ──────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

# ── Celery ────────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/2"
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# ── Celery Beat static schedule (TASK-201: weekly digest fan-out) ─────────────
# Runs daily at 08:00 UTC; the task itself filters users by their digest_day
# preference so each user receives mail only on their chosen weekday.
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    "weekly-digest-daily-fanout": {
        "task": "apps.notifications.tasks.send_weekly_digest_to_all",
        "schedule": crontab(hour=8, minute=0),  # 08:00 UTC every day
        "options": {"queue": "default"},
    },
    # TASK-305-B2: Daily AI Briefing — runs at 06:30 UTC every day
    "daily-briefing-generation": {
        "task": "apps.core.tasks.generate_daily_briefings",
        "schedule": crontab(hour=6, minute=30),  # 06:30 UTC every day
        "options": {"queue": "default"},
    },
    # TASK-502-B1: Daily database backup — runs at 02:00 UTC
    "daily-db-backup": {
        "task": "apps.core.tasks.backup_database",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "default"},
    },
    # TASK-603-B2: Knowledge graph build — runs at 05:00 UTC daily
    "daily-knowledge-graph": {
        "task": "apps.core.tasks.build_knowledge_graph",
        "schedule": crontab(hour=5, minute=0),
        "options": {"queue": "default"},
    },
    # TASK-602-B2: Daily star velocity computation — runs at 04:00 UTC
    "daily-star-velocity": {
        "task": "apps.repositories.analytics.compute_star_velocity",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "default"},
    },
}
# Track when a task transitions to STARTED (enables "processing" status in DB)
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 min hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 min soft limit
CELERY_RESULT_EXPIRES = 3600  # results expire after 1 hour
CELERY_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    # ── Automation (MUST be first — highest priority) ─────────────────────────
    # execute_workflow MUST land on 'default' so the worker that handles the
    # ▶ Run button picks it up immediately.
    "apps.automation.tasks.execute_workflow": {"queue": "default"},
    "apps.automation.tasks.cleanup_stale_runs": {"queue": "default"},
    "apps.automation.tasks.dispatch_event_trigger": {"queue": "default"},
    # ── NLP processing (Phase 2.1) ────────────────────────────────────────────
    # These MUST be listed before the 'apps.articles.tasks.*' scraping wildcard
    # below — Celery evaluates routes in definition order and the first match wins.
    "apps.articles.tasks.process_article_nlp": {"queue": "nlp"},
    "apps.articles.tasks.process_pending_articles_nlp": {"queue": "nlp"},
    # ── Summarization (Phase 2.2) ─────────────────────────────────────────────
    "apps.articles.tasks.summarize_article": {"queue": "nlp"},
    "apps.articles.tasks.summarize_pending_articles": {"queue": "nlp"},
    # ── Excerpt fetching (default queue — lightweight HTTP tasks) ─────────────
    "apps.articles.tasks.fetch_article_excerpt": {"queue": "default"},
    "apps.articles.tasks.fetch_pending_excerpts": {"queue": "default"},
    # ── Core scraping tasks ───────────────────────────────────────────────────
    "apps.core.tasks.scrape_hackernews": {"queue": "scraping"},
    "apps.core.tasks.scrape_github": {"queue": "scraping"},
    "apps.core.tasks.scrape_arxiv": {
        "queue": "slow_scraping"
    },  # long-running — isolated
    "apps.core.tasks.scrape_youtube": {
        "queue": "slow_scraping"
    },  # long-running — isolated
    "apps.core.tasks.scrape_twitter": {"queue": "scraping"},
    "apps.core.tasks.scrape_all": {"queue": "scraping"},
    "apps.core.tasks.generate_daily_briefings": {"queue": "default"},
    "apps.core.tasks.generate_user_briefing": {
        "queue": "scraping"
    },  # runs after scrapers finish
    # Legacy prefixed names (older beat entries)
    "backend.apps.core.tasks.scrape_hackernews": {"queue": "scraping"},
    "backend.apps.core.tasks.scrape_github": {"queue": "scraping"},
    "backend.apps.core.tasks.scrape_arxiv": {"queue": "slow_scraping"},
    "backend.apps.core.tasks.scrape_youtube": {"queue": "slow_scraping"},
    "backend.apps.core.tasks.scrape_twitter": {"queue": "scraping"},
    "backend.apps.core.tasks.scrape_all": {"queue": "scraping"},
    # ── Vector Embeddings (Phase 2.3) ─────────────────────────────────────────
    "apps.articles.embedding_tasks.*": {"queue": "embeddings"},
    "apps.papers.embedding_tasks.*": {"queue": "embeddings"},
    "apps.repositories.embedding_tasks.*": {"queue": "embeddings"},
    "apps.videos.embedding_tasks.*": {"queue": "embeddings"},
    "apps.tweets.embedding_tasks.*": {"queue": "embeddings"},
    # ── Agent tasks (Phase 5.1) ───────────────────────────────────────────────
    "apps.agents.tasks.*": {"queue": "agents"},
    # ── Trend analysis ────────────────────────────────────────────────────────
    "apps.trends.tasks.analyze_trends_task": {"queue": "default"},
    # ── Notifications (Phase 4.2) ─────────────────────────────────────────────
    "apps.notifications.tasks.*": {"queue": "default"},
    # ── Catch-all wildcards (MUST be last — lowest priority) ──────────────────
    # Any article/paper/repo/video task not matched above goes to scraping.
    "apps.articles.tasks.*": {"queue": "scraping"},
    "apps.papers.tasks.*": {"queue": "scraping"},
    "apps.repositories.tasks.*": {"queue": "scraping"},
    "apps.videos.tasks.*": {"queue": "scraping"},
    "apps.tweets.tasks.*": {"queue": "scraping"},
}

# ── Axes (Login Rate Limiting) ────────────────────────────────
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = None
AXES_ENABLED = True

# ── Internationalization ──────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ── Static & Media ────────────────────────────────────────────
# ── Google Drive OAuth2 (Phase 6.1) ─────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/api/v1/integrations/drive/callback/",
)

# ── AWS S3 (Phase 6.2) ───────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")


# ── Optional integration key warnings ────────────────────────────────────────
# Emit startup warnings for optional third-party integrations that are
# configured but missing required keys. These are non-fatal — features degrade
# gracefully when keys are absent — but surfacing the warning at startup is
# far better than a cryptic error at call time.
def _warn_missing_keys() -> None:
    import warnings

    _optional_keys: list[tuple[str, str]] = [
        ("GOOGLE_CLIENT_ID", "Google Drive / OAuth integration will be unavailable"),
        (
            "GOOGLE_CLIENT_SECRET",
            "Google Drive / OAuth integration will be unavailable",
        ),
        ("AWS_ACCESS_KEY_ID", "S3 storage integration will be unavailable"),
        ("AWS_SECRET_ACCESS_KEY", "S3 storage integration will be unavailable"),
        (
            "SENDGRID_API_KEY",
            "Email delivery via SendGrid will be unavailable; console backend used",
        ),
        ("STRIPE_SECRET_KEY", "Billing / Stripe integration will be unavailable"),
        ("GITHUB_CLIENT_ID", "GitHub OAuth will be unavailable"),
        ("OPENAI_API_KEY", "AI moderation and OpenAI LLM features will be unavailable"),
        ("ANTHROPIC_API_KEY", "Claude LLM support will be unavailable"),
    ]
    for key, msg in _optional_keys:
        if not os.environ.get(key):
            warnings.warn(
                f"[Synapse] {key} is not set — {msg}.",
                category=RuntimeWarning,
                stacklevel=2,
            )


_warn_missing_keys()

AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "synapse-media")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "")
AWS_PRESIGNED_URL_EXPIRY = int(os.environ.get("AWS_PRESIGNED_URL_EXPIRY", 3600))

# Use S3 for media storage when bucket is configured
if AWS_STORAGE_BUCKET_NAME and AWS_STORAGE_BUCKET_NAME != "synapse-media":
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    STATICFILES_STORAGE = "storages.backends.s3boto3.S3StaticStorage"
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
# Allow overriding via env var when backend/media/ is not writable (e.g. dev)
_media_root_env = os.environ.get("DJANGO_MEDIA_ROOT", "")
MEDIA_ROOT = Path(_media_root_env) if _media_root_env else BASE_DIR / "media"
# Sync MEDIA_ROOT back into the environment so that ai_engine/agents/doc_tools.py
# (which reads DJANGO_MEDIA_ROOT at import time) always uses the same directory
# as Django — preventing file-not-found errors on download.
os.environ.setdefault("DJANGO_MEDIA_ROOT", str(MEDIA_ROOT))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Logging ───────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "pii_redaction": {
            "()": "apps.core.log_filters.PiiRedactionFilter",
        },
    },
    "formatters": {
        "simple": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["pii_redaction"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# ── TASK-504-B1: OpenTelemetry Django auto-instrumentation ─────────────────────
# Enable with OTEL_ENABLED=true in environment.
# Install: pip install opentelemetry-distro opentelemetry-exporter-otlp-proto-grpc
#          opentelemetry-instrumentation-django opentelemetry-instrumentation-celery
#          opentelemetry-instrumentation-psycopg2 opentelemetry-instrumentation-redis
OTEL_ENABLED = os.environ.get("OTEL_ENABLED", "").lower() == "true"
if OTEL_ENABLED:
    try:
        from opentelemetry import trace  # noqa
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.celery import CeleryInstrumentor  # noqa
        from opentelemetry.instrumentation.django import DjangoInstrumentor  # noqa
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor  # noqa
        from opentelemetry.instrumentation.redis import RedisInstrumentor  # noqa
        from opentelemetry.sdk.resources import Resource  # noqa
        from opentelemetry.sdk.trace import TracerProvider  # noqa
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa

        _otel_resource = Resource.create(
            {
                "service.name": os.environ.get("OTEL_SERVICE_NAME", "synapse-backend"),
                "service.namespace": "synapse",
                "deployment.environment": os.environ.get("DJANGO_ENV", "production"),
            }
        )
        _otel_exporter = OTLPSpanExporter(
            endpoint=os.environ.get(
                "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
            ),
            insecure=True,
        )
        _otel_provider = TracerProvider(resource=_otel_resource)
        _otel_provider.add_span_processor(BatchSpanProcessor(_otel_exporter))
        trace.set_tracer_provider(_otel_provider)

        DjangoInstrumentor().instrument()
        CeleryInstrumentor().instrument()
        Psycopg2Instrumentor().instrument()
        RedisInstrumentor().instrument()
    except ImportError:
        pass  # OTel packages not installed — skip instrumentation silently

# ── TASK-506-2/3: pgBouncer connection pooling compatibility ───────────────────
# When PGBOUNCER=true, Django must use CONN_MAX_AGE=0 (no persistent connections)
# because pgBouncer transaction mode assigns connections per-transaction, not
# per-session. pgBouncer handles pooling; Django gets a fresh connection each time.
#
# To enable pgBouncer:
#   1. Set PGBOUNCER=true in environment
#   2. Set DB_HOST=pgbouncer, DB_PORT=6432 (pgBouncer listen port)
if os.environ.get("PGBOUNCER", "").lower() == "true":
    DATABASES["default"][
        "CONN_MAX_AGE"
    ] = 0  # TASK-506-3: required for transaction mode

# ── TASK-507-2: Cache headers (managed by Nginx cdn_cache.conf) ────────────────
# Static files use whitenoise for local dev; Nginx CDN config handles production caching.
# Next.js _next/static/ assets get immutable 1yr headers via infrastructure/nginx/conf.d/cdn_cache.conf
