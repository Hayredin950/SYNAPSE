"""
Celery tasks for vector embedding generation — Phase 2.3.

Tasks:
  generate_video_embedding          — Embed a single Video
  generate_pending_video_embeddings — Batch-queue unembedded Videos
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


def _build_video_text(video) -> str:
    """Build the text to embed for a Video."""
    parts = []
    if video.title:
        parts.append(video.title)
    if video.description:
        parts.append(video.description[:2000])
    if video.topics:
        parts.append(" ".join(video.topics[:10]))
    if video.transcript:
        parts.append(video.transcript[:3000])
    return " ".join(parts)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="embeddings",
    name="apps.videos.embedding_tasks.generate_video_embedding",
)
def generate_video_embedding(self, video_id: str) -> Dict:
    """
    Generate and store a vector embedding for a single Video.

    Args:
        video_id: UUID string of the Video to embed.
    """
    task_id = self.request.id
    logger.info("[%s] Generating embedding for video: %s", task_id, video_id)
    start_time = time.time()

    try:
        from apps.videos.models import Video  # noqa: PLC0415

        try:
            video = Video.objects.get(pk=video_id)
        except Video.DoesNotExist:
            logger.error("[%s] Video %s not found.", task_id, video_id)
            return {"status": "error", "reason": "not_found", "video_id": video_id}

        text = _build_video_text(video)
        if not text.strip():
            return {"status": "skipped", "reason": "no_content", "video_id": video_id}

        embedder = _get_embedder()
        vector = embedder.embed(text)

        video.embedding = vector
        video.save(update_fields=["embedding"])

        elapsed = round(time.time() - start_time, 2)
        logger.info("[%s] Embedded video %s in %.2fs", task_id, video_id, elapsed)
        return {
            "status": "success",
            "video_id": video_id,
            "dimensions": len(vector),
            "elapsed_seconds": elapsed,
        }

    except Exception as exc:
        logger.error("[%s] Error embedding video %s: %s", task_id, video_id, exc)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(
    bind=True,
    max_retries=1,
    queue="embeddings",
    name="apps.videos.embedding_tasks.generate_pending_video_embeddings",
)
def generate_pending_video_embeddings(self, batch_size: int = 100) -> Dict:
    """Queue embedding for Videos without an embedding."""
    task_id = self.request.id
    try:
        from apps.videos.models import Video  # noqa: PLC0415

        pending_ids = list(
            Video.objects.filter(embedding__isnull=True).values_list("id", flat=True)[
                :batch_size
            ]
        )
        for video_id in pending_ids:
            generate_video_embedding.delay(str(video_id))

        logger.info("[%s] Queued %d video embedding tasks.", task_id, len(pending_ids))
        return {"status": "success", "queued": len(pending_ids)}

    except Exception as exc:
        logger.error("[%s] generate_pending_video_embeddings failed: %s", task_id, exc)
        raise self.retry(exc=exc, countdown=120)
