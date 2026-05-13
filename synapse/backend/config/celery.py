"""
Celery configuration for SYNAPSE.

Configures Celery for asynchronous task execution with:
- Redis broker (from CELERY_BROKER_URL / REDIS_URL environment variable)
- Redis result backend
- Django-Celery-Beat for scheduled tasks
- JSON serialization
- UTC timezone
- Task routing to specific queues

NOTE: All core Celery settings (broker, backend, serialization, task_routes, etc.)
are defined in config/settings/base.py and loaded via config_from_object below.
This file only defines the Celery app, autodiscovers tasks, and sets the beat
schedule (which is harder to express purely in Django settings).
"""

# ── Langchain compatibility patch ─────────────────────────────────────────────
# langchain-openai >= 0.2.14 needs ContextOverflowError from langchain-core,
# which is missing in langchain-core 0.3.83. Patch it before any task imports.
import sys
try:
    from langchain_core import exceptions as _lc_exc

    if not hasattr(_lc_exc, "ContextOverflowError"):

        class _ContextOverflowError(_lc_exc.LangChainException):
            """Context window exceeded — compatibility shim."""

        _lc_exc.ContextOverflowError = _ContextOverflowError
        print("[celery] Applied langchain ContextOverflowError compatibility patch")
except ImportError as e:
    # langchain-core not installed — expected if langchain-openai isn't used
    print(f"[celery] WARNING: Could not apply langchain patch (langchain-core not available): {e}")
except Exception as e:
    # Unexpected error — log it but don't crash (might be optional)
    print(f"[celery] WARNING: Unexpected error while patching langchain: {e}", file=sys.stderr)
# ─────────────────────────────────────────────────────────────────────────────
import os

from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Create Celery app instance
app = Celery("synapse")

# Load ALL configuration from Django settings (namespace='CELERY' means Django
# settings prefixed with CELERY_ are mapped to Celery config keys).
# This is the single source of truth — do NOT call app.conf.update() after this
# to avoid overwriting the settings-defined values (broker URL, task_routes, etc.)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all INSTALLED_APPS
app.autodiscover_tasks()

# Beat scheduler configuration (django-celery-beat)
# Defined here (not in settings) because crontab imports require Celery to be
# initialised first.  The CELERY_ prefix is NOT used here — beat_schedule is
# applied directly on the app after config is loaded.
CELERY_BEAT_SCHEDULE = {
    # ── HackerNews — every 30 minutes ────────────────────────────────────────
    "scrape-hackernews-every-30min": {
        "task": "apps.core.tasks.scrape_hackernews",
        "schedule": 30 * 60,
        "args": ("top", 100),
        "options": {"queue": "scraping"},
    },
    # Also scrape "new" stories every 2 hours for fresher content
    "scrape-hackernews-new-every-2hrs": {
        "task": "apps.core.tasks.scrape_hackernews",
        "schedule": 2 * 60 * 60,
        "args": ("new", 50),
        "options": {"queue": "scraping"},
    },
    # ── GitHub — every 2 hours ────────────────────────────────────────────────
    "scrape-github-every-2hrs": {
        "task": "apps.core.tasks.scrape_github",
        "schedule": 2 * 60 * 60,
        "args": (1, None, 100),  # days_back=1, language=None, limit=100
        "options": {"queue": "scraping"},
    },
    # Also scrape Python-specific repos every 4 hours
    "scrape-github-python-every-4hrs": {
        "task": "apps.core.tasks.scrape_github",
        "schedule": 4 * 60 * 60,
        "args": (1, "Python", 50),
        "options": {"queue": "scraping"},
    },
    # Also scrape TypeScript repos every 4 hours (offset by 1hr)
    "scrape-github-typescript-every-4hrs": {
        "task": "apps.core.tasks.scrape_github",
        "schedule": crontab(minute=0, hour="1,5,9,13,17,21"),
        "args": (1, "TypeScript", 50),
        "options": {"queue": "scraping"},
    },
    # ── arXiv — every 6 hours ────────────────────────────────────────────────
    "scrape-arxiv-every-6hrs": {
        "task": "apps.core.tasks.scrape_arxiv",
        "schedule": 6 * 60 * 60,
        "args": (None, 7, 500),  # categories=None, days_back=7, max_papers=500
        "options": {"queue": "slow_scraping"},
    },
    # ── YouTube — every 6 hours (was 12hrs, 8 queries now completes in ~34s) ─
    "scrape-youtube-every-6hrs": {
        "task": "apps.core.tasks.scrape_youtube",
        "schedule": 6 * 60 * 60,
        "args": (30, 40),  # days_back=30, max_results=40 (5 per query)
        "options": {"queue": "slow_scraping"},
    },
    # ── X/Twitter via official API v2 — every 4 hours ────────────────────────
    # NOTE: Nitter is removed (dead tech). Use Twitter API v2 Bearer Token.
    # Requires TWITTER_BEARER_TOKEN env var. Set use_nitter=False.
    "scrape-twitter-ai-every-4hrs": {
        "task": "apps.core.tasks.scrape_twitter",
        "schedule": crontab(minute=30, hour="0,4,8,12,16,20"),
        "kwargs": {
            "max_results": 50,
            "query": "AI machine learning LLM",
            "use_nitter": False,
        },
        "options": {"queue": "scraping"},
    },
    # Python/programming tweets every 4 hours (offset)
    "scrape-twitter-python-every-4hrs": {
        "task": "apps.core.tasks.scrape_twitter",
        "schedule": crontab(minute=0, hour="2,6,10,14,18,22"),
        "kwargs": {
            "max_results": 50,
            "query": "Python programming open source",
            "use_nitter": False,
        },
        "options": {"queue": "scraping"},
    },
    # Tweet embeddings — generate vectors for newly scraped tweets every hour
    "embed-pending-tweets-every-hour": {
        "task": "apps.tweets.embedding_tasks.generate_pending_tweet_embeddings",
        "schedule": 60 * 60,
        "args": (100,),
        "options": {"queue": "embeddings"},
    },
    # NLP processing — Phase 2.1
    # Run every 30 minutes to prevent queue overload
    "process-pending-nlp-every-30min": {
        "task": "apps.articles.tasks.process_pending_articles_nlp",
        "schedule": 30 * 60,  # 30 minutes in seconds
        "args": (10,),  # batch_size=10 (matches default)
        "options": {"queue": "nlp"},
    },
    # Summarization catch-up — Phase 2.2
    # Runs every 15 minutes to summarize articles that missed the pipeline
    # (e.g. imported before Phase 2.2, or whose summarization failed)
    "fetch-pending-excerpts-every-5min": {
        "task": "apps.articles.tasks.fetch_pending_excerpts",
        "schedule": 5 * 60,  # every 5 minutes — fast HTTP fetches, not Gemini
        "options": {"queue": "default"},  # separate from nlp so Gemini can't block it
    },
    "summarize-pending-articles-every-15min": {
        "task": "apps.articles.tasks.summarize_pending_articles",
        "schedule": 15 * 60,  # 15 minutes in seconds
        "args": (20,),  # batch_size=20
        "options": {"queue": "nlp"},
    },
    # Phase 4.1 — Workflow Engine
    # Periodic cleanup: mark stale 'running' workflow runs as failed (every hour)
    "cleanup-stale-workflow-runs-every-hour": {
        "task": "apps.automation.tasks.cleanup_stale_runs",
        "schedule": 60 * 60,  # 1 hour
        "options": {"queue": "default"},
    },
    # Phase 4.2 — Notifications: poll for unread count every 5 minutes via Celery
    # (Frontend uses polling via React Query — no WebSocket needed for MVP)
    # Phase 2.4 / 9 — Technology Trend Analysis
    # Runs daily at 00:05 UTC — uses days_back=30 so it always finds data
    "analyze-trends-daily": {
        "task": "apps.trends.tasks.analyze_trends_task",
        "schedule": crontab(hour=0, minute=5),  # 00:05 UTC daily
        "kwargs": {"days_back": 30},
        "options": {"queue": "default"},
    },
    # Also re-run trends at noon so fresh scraped data is reflected same day
    "analyze-trends-midday": {
        "task": "apps.trends.tasks.analyze_trends_task",
        "schedule": crontab(hour=12, minute=5),  # 12:05 UTC daily
        "kwargs": {"days_back": 30},
        "options": {"queue": "default"},
    },
}

# Apply only the beat schedule — all other config comes from Django settings
# via config_from_object above.  Applying a partial update here would
# overwrite settings-defined values (broker URL, task_routes, etc.) with
# stale/wrong defaults, causing tasks to stay in "pending".
app.conf.beat_schedule = CELERY_BEAT_SCHEDULE


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    print(f"Request: {self.request!r}")
