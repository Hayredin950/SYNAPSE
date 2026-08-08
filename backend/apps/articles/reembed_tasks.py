"""
backend.apps.articles.reembed_tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Celery task to re-embed all articles with the new BAAI/bge-large-en-v1.5 model (1024 dims).

Run once after migrating the embedding column to vector(1024):
    celery -A config.celery call apps.articles.reembed_tasks.reembed_all_articles

TASK-005-B3
"""

from __future__ import annotations

import logging
import os

import httpx

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="articles.reembed_all_articles", max_retries=3)
def reembed_all_articles(self, batch_size: int = 32) -> dict:
    """
    Re-embed all articles using the current EMBEDDING_MODEL (bge-large-en-v1.5, 1024 dims).

    Fetches articles in batches of `batch_size`, generates new embeddings,
    and saves them to the DB. Skips articles with no content.

    Returns: dict with total, embedded, skipped counts.
    """
    from apps.articles.models import Article

    AI_ENGINE_URL = os.environ.get("AI_ENGINE_URL", "http://localhost:8001")

    articles = (
        Article.objects.filter(content__isnull=False).exclude(content="").order_by("id")
    )
    total = articles.count()
    embedded = 0
    skipped = 0

    logger.info(
        "reembed_all_articles: starting — total=%d batch_size=%d", total, batch_size
    )

    for i in range(0, total, batch_size):
        batch = list(articles[i : i + batch_size])
        texts = []
        valid = []

        for article in batch:
            text = f"{article.title or ''} {article.content or ''}"[:8192].strip()
            if text:
                texts.append(text)
                valid.append(article)
            else:
                skipped += 1

        if not texts:
            continue

        try:
            resp = httpx.post(
                f"{AI_ENGINE_URL}/embeddings",
                json={"texts": texts},
                timeout=120,
            )
            resp.raise_for_status()
            embeddings = resp.json()["embeddings"]

            for article, embedding in zip(valid, embeddings):
                article.embedding = embedding
            Article.objects.bulk_update(valid, ["embedding"])
            embedded += len(valid)
            logger.info(
                "reembed_all_articles: progress %d/%d (embedded=%d skipped=%d)",
                i + len(batch),
                total,
                embedded,
                skipped,
            )
        except Exception as exc:
            logger.error("reembed_all_articles: batch %d failed: %s", i, exc)

    logger.info(
        "reembed_all_articles: complete — total=%d embedded=%d skipped=%d",
        total,
        embedded,
        skipped,
    )
    return {"total": total, "embedded": embedded, "skipped": skipped}
