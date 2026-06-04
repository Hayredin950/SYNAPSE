"""
Celery tasks for vector embedding generation — Tweets / X.

Tasks:
  generate_tweet_embedding          — Embed a single Tweet
  generate_pending_tweet_embeddings — Batch-queue unembedded Tweets
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
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from ai_engine.embeddings import get_embedder  # noqa: PLC0415

    return get_embedder()


def _build_tweet_text(tweet) -> str:
    """Build the text to embed for a Tweet."""
    parts = []
    if tweet.text:
        parts.append(tweet.text)
    if tweet.author_username:
        parts.append(f"@{tweet.author_username}")
    if tweet.author_display_name:
        parts.append(tweet.author_display_name)
    if tweet.hashtags:
        parts.append(" ".join(f"#{h}" for h in tweet.hashtags[:20]))
    if tweet.topic:
        parts.append(tweet.topic)
    return " ".join(parts)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="embeddings",
    name="apps.tweets.embedding_tasks.generate_tweet_embedding",
)
def generate_tweet_embedding(self, tweet_id: str) -> Dict:
    """
    Generate and store a vector embedding for a single Tweet.

    Args:
        tweet_id: UUID string of the Tweet to embed.
    """
    task_id = self.request.id
    logger.info("[%s] Generating embedding for tweet: %s", task_id, tweet_id)
    start_time = time.time()

    try:
        from apps.tweets.models import Tweet  # noqa: PLC0415

        try:
            tweet = Tweet.objects.get(pk=tweet_id)
        except Tweet.DoesNotExist:
            logger.error("[%s] Tweet %s not found.", task_id, tweet_id)
            return {"status": "error", "reason": "not_found", "tweet_id": tweet_id}

        text = _build_tweet_text(tweet)
        if not text.strip():
            return {"status": "skipped", "reason": "no_content", "tweet_id": tweet_id}

        embedder = _get_embedder()
        vector = embedder.embed(text)

        tweet.embedding = vector
        tweet.save(update_fields=["embedding"])

        elapsed = round(time.time() - start_time, 2)
        logger.info("[%s] Embedded tweet %s in %.2fs", task_id, tweet_id, elapsed)
        return {
            "status": "success",
            "tweet_id": tweet_id,
            "dimensions": len(vector),
            "elapsed_seconds": elapsed,
        }

    except Exception as exc:
        logger.error("[%s] Error embedding tweet %s: %s", task_id, tweet_id, exc)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(
    bind=True,
    max_retries=1,
    queue="embeddings",
    name="apps.tweets.embedding_tasks.generate_pending_tweet_embeddings",
)
def generate_pending_tweet_embeddings(self, batch_size: int = 100) -> Dict:
    """Queue embedding tasks for Tweets without an embedding."""
    task_id = self.request.id
    try:
        from apps.tweets.models import Tweet  # noqa: PLC0415

        pending_ids = list(
            Tweet.objects.filter(embedding__isnull=True).values_list("id", flat=True)[
                :batch_size
            ]
        )
        for tid in pending_ids:
            generate_tweet_embedding.delay(str(tid))

        logger.info("[%s] Queued %d tweet embedding tasks.", task_id, len(pending_ids))
        return {"status": "success", "queued": len(pending_ids)}

    except Exception as exc:
        logger.error("[%s] generate_pending_tweet_embeddings failed: %s", task_id, exc)
        raise self.retry(exc=exc, countdown=120)
