"""
automation.signals
~~~~~~~~~~~~~~~~~~
Django signals that wire system events to the automation event trigger pipeline.

When a new Article/ResearchPaper/Repository is saved or a trending topic spikes,
`dispatch_event_trigger` is called so any matching event-triggered workflows fire.

Signal connections are registered in AutomationConfig.ready().
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import Signal, receiver

logger = logging.getLogger(__name__)

# Custom signal for trending spikes (fired by the trends task)
trending_spike_signal = Signal()  # provides: topic, score, language


def _fire_event(event_type: str, payload: dict) -> None:
    """Queue the dispatch task asynchronously — never blocks the caller."""
    try:
        from .tasks import dispatch_event_trigger

        dispatch_event_trigger.delay(event_type, payload)
    except Exception as exc:
        logger.warning("_fire_event: could not dispatch '%s': %s", event_type, exc)


# ── New Article ────────────────────────────────────────────────────────────────


def _on_new_article(sender, instance, created, **kwargs):
    if not created:
        return
    # `instance.source` is a ForeignKey → returns a `Source` *object*, which is
    # not JSON-serializable. Celery's JSON serializer chokes on it and the
    # signal fires hundreds of times per minute during scrapes, flooding logs
    # AND consuming Render's already-tight 512 MB free-tier memory budget.
    # Convert it to plain strings here.
    src = getattr(instance, "source", None)
    source_name = ""
    source_id = None
    if src is not None:
        # `name` is the canonical display field on the Source model; fall back
        # to str() if the field shape ever changes.
        source_name = getattr(src, "name", None) or str(src)
        source_id = str(getattr(src, "id", "")) or None

    _fire_event(
        "new_article",
        {
            "article_id": str(instance.id),
            "title": instance.title or "",
            "source": source_name,
            "source_id": source_id,
            "topic": getattr(instance, "topic", "") or "",
            "url": getattr(instance, "url", "") or "",
        },
    )


# ── New Research Paper ────────────────────────────────────────────────────────


def _on_new_paper(sender, instance, created, **kwargs):
    if not created:
        return
    _fire_event(
        "new_paper",
        {
            "paper_id": str(instance.id),
            "title": instance.title,
            "topic": getattr(instance, "topic", "") or "",
            "url": getattr(instance, "url", ""),
        },
    )


# ── New Trending Repository ───────────────────────────────────────────────────


def _on_new_repo(sender, instance, created, **kwargs):
    if not created:
        return
    _fire_event(
        "new_repo",
        {
            "repo_id": str(instance.id),
            "name": instance.name,
            "language": getattr(instance, "language", ""),
            "topic": getattr(instance, "topic", "") or "",
            "url": getattr(instance, "url", ""),
        },
    )


# ── Trending Spike (custom signal) ────────────────────────────────────────────


def _on_trending_spike(sender, topic, score, language="", **kwargs):
    _fire_event(
        "trending_spike",
        {
            "topic": topic,
            "score": score,
            "language": language,
        },
    )


def connect_signals():
    """
    Connect all signals. Called from AutomationConfig.ready().
    Uses lazy imports to avoid AppRegistryNotReady errors.
    """
    try:
        from apps.articles.models import Article

        post_save.connect(
            _on_new_article,
            sender=Article,
            weak=False,
            dispatch_uid="automation_new_article",
        )
        logger.debug("automation: connected new_article signal")
    except Exception as exc:
        logger.warning("automation signals: could not connect Article: %s", exc)

    try:
        from apps.papers.models import ResearchPaper

        post_save.connect(
            _on_new_paper,
            sender=ResearchPaper,
            weak=False,
            dispatch_uid="automation_new_paper",
        )
        logger.debug("automation: connected new_paper signal")
    except Exception as exc:
        logger.warning("automation signals: could not connect ResearchPaper: %s", exc)

    try:
        from apps.repositories.models import Repository

        post_save.connect(
            _on_new_repo,
            sender=Repository,
            weak=False,
            dispatch_uid="automation_new_repo",
        )
        logger.debug("automation: connected new_repo signal")
    except Exception as exc:
        logger.warning("automation signals: could not connect Repository: %s", exc)

    trending_spike_signal.connect(
        _on_trending_spike, weak=False, dispatch_uid="automation_trending_spike"
    )
    logger.debug("automation: connected trending_spike signal")
