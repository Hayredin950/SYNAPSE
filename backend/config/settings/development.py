from datetime import timedelta

from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# ── JWT — longer token lifetime in dev so polling never hits 401 mid-run ──────
# Production keeps 15 min (set via JWT_ACCESS_TOKEN_LIFETIME_MINUTES env var).
# In development we use 60 min so a workflow run never causes token expiry.
SIMPLE_JWT = {
    **SIMPLE_JWT,
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# ── django.contrib.postgres is required for ArrayField ──────────────────────
# Must be included when using PostgreSQL (ArrayField, HStoreField, etc.)
if "django.contrib.postgres" not in INSTALLED_APPS:
    INSTALLED_APPS = list(INSTALLED_APPS) + ["django.contrib.postgres"]

# Allow only localhost origins in development — mirrors production model.
# CORS_ALLOW_ALL_ORIGINS=True would allow any origin (including malicious sites)
# to make credentialed requests to the API. Restrict to known dev origins instead.
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",  # alternate dev port
    "http://127.0.0.1:3001",
]

# Disable axes in development for convenience
AXES_ENABLED = False

# Disable throttling in development/test to prevent 429s during test runs
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}

# Show SQL queries in development
LOGGING["loggers"]["django.db.backends"] = {
    "handlers": ["console"],
    "level": "WARNING",  # set to DEBUG to see SQL, WARNING to reduce noise
    "propagate": False,
}
