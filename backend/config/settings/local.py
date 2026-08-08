"""
Local development settings — uses SQLite so no Postgres/Redis needed.
Run with: DJANGO_SETTINGS_MODULE=config.settings.local python manage.py runserver
"""

# Monkey-patch ArrayField -> JSONField before any app models load
import django.contrib.postgres.fields as _pg_fields
from django.db.models import JSONField as _JSONField


class _ArrayFieldShim(_JSONField):
    """Drop-in replacement for ArrayField that works with SQLite."""

    def __init__(self, base_field=None, size=None, **kwargs):
        kwargs.setdefault("default", list)
        super().__init__(**kwargs)


_pg_fields.ArrayField = _ArrayFieldShim

from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True

# ── SQLite (no Postgres required) ─────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ── Disable Redis-dependent features ─────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Celery: run tasks synchronously (no broker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ── Disable optional third-party apps that need extra setup ──────────────────
INSTALLED_APPS = [
    app
    for app in INSTALLED_APPS
    if app
    not in (
        "django_prometheus",
        "silk",
        "django_celery_beat",
        "django_celery_results",
    )
]

# ── Disable axes in local dev ─────────────────────────────────────────────────
AXES_ENABLED = False

# ── Simple logging ────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
