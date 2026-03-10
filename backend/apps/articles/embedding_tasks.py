"""
Celery tasks for vector embedding generation — Phase 2.3.

Tasks:
  generate_article_embedding        — Embed a single Article
  generate_pending_article_embeddings — Batch-queue unembedded Articles
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Dict

from celery import shared_task

logger = logging.getLogger(__name__)


def _get_embedder():
    """Import and return the SynapseEmbedder singleton."""
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from ai_engine.embeddings import get_embedder  # noqa: PLC0415

    return get_embedder()


def _build_article_text(article) -> str:
    """Build the text to embed for an Article."""
    parts = []
    if article.title:
        parts.append(article.title)
    if article.summary:
        parts.append(article.summary)
    elif article.content:
        parts.append(article.content[:2000])
    if article.topic:
        parts.append(article.topic)
    if article.keywords:
        parts.append(" ".join(article.keywords[:10]))
    return " ".join(parts)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="embeddings",
    name="apps.articles.embedding_tasks.generate_article_embedding",
)
def generate_article_embedding(self, article_id: str) -> Dict:
    """
    Generate and store a vector embedding for a single Article.

    Args:
        article_id: UUID string of the Article to embed.

    Returns:
        Dict with status and embedding metadata.
    """
    task_id = self.request.id
    logger.info("[%s] Generating embedding for article: %s", task_id, article_id)
    start_time = time.time()

    try:
        from apps.articles.models import Article  # noqa: PLC0415

        try:
            article = Article.objects.get(pk=article_id)
        except Article.DoesNotExist:
            logger.error("[%s] Article %s not found.", task_id, article_id)
            return {"status": "error", "reason": "not_found", "article_id": article_id}

        text = _build_article_text(article)
        if not text.strip():
            logger.warning("[%s] Article %s has no text to embed.", task_id, article_id)
            return {
                "status": "skipped",
                "reason": "no_content",
                "article_id": article_id,
            }

        embedder = _get_embedder()
        vector = embedder.embed(text)

        article.embedding = vector
        article.save(update_fields=["embedding", "updated_at"])

        elapsed = round(time.time() - start_time, 2)
        logger.info(
            "[%s] Embedded article %s in %.2fs (dims=%d)",
            task_id,
            article_id,
            elapsed,
            len(vector),
        )
        return {
            "status": "success",
            "article_id": article_id,
            "dimensions": len(vector),
            "elapsed_seconds": elapsed,
        }

    except Exception as exc:
        logger.error("[%s] Error embedding article %s: %s", task_id, article_id, exc)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(
    bind=True,
    max_retries=1,
    queue="embeddings",
    name="apps.articles.embedding_tasks.generate_pending_article_embeddings",
)
def generate_pending_article_embeddings(self, batch_size: int = 100) -> Dict:
    """
    Queue embedding generation for Articles that have no embedding yet.

    Args:
        batch_size: Maximum number of articles to enqueue (default 100).
    """
    task_id = self.request.id
    logger.info(
        "[%s] Queuing embeddings for pending articles (batch=%d)", task_id, batch_size
    )

    try:
        from apps.articles.models import Article  # noqa: PLC0415

        pending_ids = list(
            Article.objects.filter(embedding__isnull=True).values_list("id", flat=True)[
                :batch_size
            ]
        )

        for article_id in pending_ids:
            generate_article_embedding.delay(str(article_id))

        logger.info(
            "[%s] Queued %d article embedding tasks.", task_id, len(pending_ids)
        )
        return {"status": "success", "queued": len(pending_ids)}

    except Exception as exc:
        logger.error(
            "[%s] generate_pending_article_embeddings failed: %s", task_id, exc
        )
        raise self.retry(exc=exc, countdown=120)
