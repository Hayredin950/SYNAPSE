"""
SYNAPSE Django settings for Replit development environment.
Inherits from development.py but overrides Redis/Celery to use in-memory backends.
"""

from .development import *  # noqa: F401, F403
import os

# Override ALLOWED_HOSTS for Replit proxy
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# ── Use in-memory channel layer (no Redis needed) ─────────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# ── Redis cache — try real Redis first, fall back to LocMemCache ─────────────
import subprocess as _subprocess

def _redis_running() -> bool:
    try:
        import socket
        s = socket.create_connection(("127.0.0.1", 6379), timeout=1)
        s.close()
        return True
    except Exception:
        return False

if _redis_running():
    CACHES = {
        "default": {
            "BACKEND":  "django_redis.cache.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/0",
            "OPTIONS": {
                "CLIENT_CLASS":          "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 2,
                "SOCKET_TIMEOUT":         2,
                "IGNORE_EXCEPTIONS":      True,
            },
            "KEY_PREFIX": "synapse",
            "TIMEOUT":    300,
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"
else:
    CACHES = {
        "default": {
            "BACKEND":  "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "synapse-default",
        }
    }

# ── Celery — use Redis broker if available, otherwise in-memory ───────────────
if _redis_running():
    CELERY_BROKER_URL      = "redis://127.0.0.1:6379/1"
    CELERY_RESULT_BACKEND  = "redis://127.0.0.1:6379/2"
    CELERY_ALWAYS_EAGER    = False
    CELERY_TASK_ALWAYS_EAGER = False
else:
    CELERY_BROKER_URL      = "memory://"
    CELERY_RESULT_BACKEND  = "cache+memory://"
    CELERY_ALWAYS_EAGER    = True
    CELERY_EAGER_PROPAGATES = True
    CELERY_TASK_ALWAYS_EAGER = True

# ── Database (Replit PostgreSQL) ───────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "heliumdb"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "password"),
        "HOST": os.environ.get("DB_HOST", "helium"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}

# ── Disable Silk profiler ──────────────────────────────────────────────────────
SILKY_PYTHON_PROFILER = False
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "silk"]
MIDDLEWARE = [m for m in MIDDLEWARE if "silk" not in m.lower()]

# ── Disable Axes login throttling in dev ──────────────────────────────────────
AXES_ENABLED = False

# ── Disable throttling ────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}

# ── Disable Sentry ────────────────────────────────────────────────────────────
SENTRY_DSN = None

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"

# ── Media files ───────────────────────────────────────────────────────────────
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"

# ── CORS for Next.js dev server ───────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:22167",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:22167",
]
CORS_ALLOW_ALL_ORIGINS = True

# ── JWT settings ───────────────────────────────────────────────────────────────
from datetime import timedelta  # noqa: E402
SIMPLE_JWT = {
    **SIMPLE_JWT,
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# ── Disable email sending (use console backend) ────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ── Relax password validators for dev/demo environment ────────────────────────
# Remove strict validators so users can register with simple passwords
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]

# ── Dev-only: skip email verification requirement ─────────────────────────────
# In Replit we use the console email backend so real emails never arrive.
# Setting this to True makes RegisterView auto-verify and issue JWT tokens
# immediately on signup so users can use the app without an inbox.
AUTO_VERIFY_EMAIL = True

# ── Dev-only: generous registration throttle ──────────────────────────────────
# The default 5/hour limit is too restrictive for iterative testing.
REGISTRATION_THROTTLE_RATE = "1000/hour"

# ── Replit AI integration — OpenAI-compatible endpoint ────────────────────────
# Used for article summarization, daily briefings, and the AI agent.
# No real API key needed — Replit's modelfarm proxies the requests.
_replit_ai_base = os.environ.get(
    "AI_INTEGRATIONS_OPENAI_BASE_URL", "http://localhost:1106/modelfarm/openai"
)
_replit_ai_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "_DUMMY_API_KEY_")

# Wire into the summarizer provider resolver (checked after Groq, before nothing)
OPENROUTER_API_KEY = _replit_ai_key
OPENROUTER_BASE_URL = _replit_ai_base
OPENROUTER_MODEL = "gpt-4o-mini"

# Wire into the agent LLM factory
OPENAI_API_KEY = _replit_ai_key
OPENAI_API_BASE = _replit_ai_base
