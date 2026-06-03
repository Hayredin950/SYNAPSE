"""
backend.apps.core.analytics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Analytics event tracking — PostHog server-side + custom Prometheus business metrics.

Phase 9.2 — Monitoring & Analytics

PostHog: privacy-first product analytics (self-hostable, GDPR compliant)
  - Tracks: signups, logins, AI queries, document generation, bookmarks,
    automation runs, searches, article/repo/paper views
  - Identify + group calls for user segmentation

Prometheus custom counters (business metrics):
  - synapse_user_signups_total
  - synapse_ai_queries_total
  - synapse_documents_generated_total
  - synapse_articles_scraped_total
  - synapse_searches_total
  - synapse_bookmarks_total
  - synapse_automation_runs_total
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

# ── PostHog client (lazy singleton) ───────────────────────────────────────────

POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY", "")
POSTHOG_HOST = os.environ.get("POSTHOG_HOST", "https://app.posthog.com")
ANALYTICS_ENABLED = (
    bool(POSTHOG_API_KEY) and os.environ.get("ANALYTICS_ENABLED", "true") == "true"
)

_posthog_client = None


def _get_posthog():
    """Return PostHog client (lazy init, None if not configured)."""
    global _posthog_client
    if not ANALYTICS_ENABLED:
        return None
    if _posthog_client is None:
        try:
            from posthog import Posthog

            _posthog_client = Posthog(
                api_key=POSTHOG_API_KEY,
                host=POSTHOG_HOST,
                sync_mode=False,  # async — non-blocking
                disabled=not ANALYTICS_ENABLED,
                on_error=lambda e, _: logger.warning("posthog_error", error=str(e)),
            )
            logger.info("posthog_client_initialized", host=POSTHOG_HOST)
        except ImportError:
            logger.warning("posthog_not_installed", hint="pip install posthog")
    return _posthog_client


# ── Prometheus business metrics ────────────────────────────────────────────────


def _make_counter(name: str, description: str, labels: list[str] = None):
    """Create a Prometheus Counter, returning a no-op callable if prometheus_client not installed."""
    try:
        from prometheus_client import Counter

        if labels:
            return Counter(name, description, labels)
        return Counter(name, description)
    except ImportError:

        class _Noop:
            def labels(self, **_):
                return self

            def inc(self, *_, **__):
                pass

        return _Noop()


# Business metric counters
METRIC_SIGNUPS = _make_counter(
    "synapse_user_signups_total", "Total user registrations", ["plan"]
)
METRIC_LOGINS = _make_counter(
    "synapse_user_logins_total", "Total user logins", ["method"]
)
METRIC_AI_QUERIES = _make_counter(
    "synapse_ai_queries_total", "Total AI chat/agent queries", ["type"]
)
METRIC_DOCS_GENERATED = _make_counter(
    "synapse_documents_generated_total", "Total documents generated", ["doc_type"]
)
METRIC_ARTICLES_SCRAPED = _make_counter(
    "synapse_articles_scraped_total", "Total articles scraped", ["source"]
)
METRIC_SEARCHES = _make_counter(
    "synapse_searches_total", "Total searches performed", ["search_type"]
)
METRIC_BOOKMARKS = _make_counter(
    "synapse_bookmarks_total", "Total bookmark toggles", ["content_type", "action"]
)
METRIC_AUTOMATION_RUNS = _make_counter(
    "synapse_automation_runs_total", "Total automation workflow runs", ["status"]
)
METRIC_DRIVE_UPLOADS = _make_counter(
    "synapse_drive_uploads_total", "Total Google Drive uploads"
)
METRIC_S3_UPLOADS = _make_counter("synapse_s3_uploads_total", "Total S3 uploads")


# ── Event tracking functions ───────────────────────────────────────────────────


def track_signup(
    user_id: str, email: str, plan: str = "free", properties: dict = None
) -> None:
    """Track a new user registration."""
    METRIC_SIGNUPS.labels(plan=plan).inc()
    ph = _get_posthog()
    if ph:
        ph.identify(str(user_id), {"email": email, "plan": plan})
        ph.capture(
            str(user_id),
            "user_signed_up",
            {
                "plan": plan,
                **(properties or {}),
            },
        )
    logger.info("analytics_signup", user_id=user_id, plan=plan)


def track_login(user_id: str, method: str = "email") -> None:
    """Track user login."""
    METRIC_LOGINS.labels(method=method).inc()
    ph = _get_posthog()
    if ph:
        ph.capture(str(user_id), "user_logged_in", {"method": method})


def track_ai_query(
    user_id: str, query_type: str = "chat", model: str = "", tokens: int = 0
) -> None:
    """Track AI chat or agent query."""
    METRIC_AI_QUERIES.labels(type=query_type).inc()
    ph = _get_posthog()
    if ph:
        ph.capture(
            str(user_id),
            "ai_query",
            {
                "query_type": query_type,
                "model": model,
                "tokens": tokens,
            },
        )


def track_document_generated(user_id: str, doc_type: str, title: str = "") -> None:
    """Track document generation."""
    METRIC_DOCS_GENERATED.labels(doc_type=doc_type).inc()
    ph = _get_posthog()
    if ph:
        ph.capture(
            str(user_id),
            "document_generated",
            {
                "doc_type": doc_type,
                "title": title,
            },
        )


def track_search(
    user_id: str, query: str, search_type: str = "keyword", results: int = 0
) -> None:
    """Track search query."""
    METRIC_SEARCHES.labels(search_type=search_type).inc()
    ph = _get_posthog()
    if ph:
        ph.capture(
            str(user_id),
            "search_performed",
            {
                "query": query[:200],  # truncate for privacy
                "search_type": search_type,
                "result_count": results,
            },
        )


def track_bookmark(user_id: str, content_type: str, action: str = "add") -> None:
    """Track bookmark add/remove."""
    METRIC_BOOKMARKS.labels(content_type=content_type, action=action).inc()
    ph = _get_posthog()
    if ph:
        ph.capture(
            str(user_id),
            "bookmark_toggled",
            {
                "content_type": content_type,
                "action": action,
            },
        )


def track_article_scraped(source: str = "hackernews") -> None:
    """Track article ingestion (called from Celery tasks)."""
    METRIC_ARTICLES_SCRAPED.labels(source=source).inc()


def track_automation_run(
    user_id: str, workflow_name: str, status: str = "success"
) -> None:
    """Track automation workflow execution."""
    METRIC_AUTOMATION_RUNS.labels(status=status).inc()
    ph = _get_posthog()
    if ph:
        ph.capture(
            str(user_id),
            "automation_run",
            {
                "workflow": workflow_name,
                "status": status,
            },
        )


def track_drive_upload(user_id: str, doc_type: str) -> None:
    """Track Google Drive upload."""
    METRIC_DRIVE_UPLOADS.inc()
    ph = _get_posthog()
    if ph:
        ph.capture(str(user_id), "drive_upload", {"doc_type": doc_type})


def track_s3_upload(user_id: str, doc_type: str) -> None:
    """Track S3 upload."""
    METRIC_S3_UPLOADS.inc()
    ph = _get_posthog()
    if ph:
        ph.capture(str(user_id), "s3_upload", {"doc_type": doc_type})


def identify_user(user_id: str, properties: dict) -> None:
    """
    Identify a user in PostHog with profile properties.
    Call after login or profile update.
    """
    ph = _get_posthog()
    if ph:
        ph.identify(str(user_id), properties)


def flush_analytics() -> None:
    """Flush PostHog queue (call in Celery shutdown or test teardown)."""
    ph = _get_posthog()
    if ph:
        ph.flush()
