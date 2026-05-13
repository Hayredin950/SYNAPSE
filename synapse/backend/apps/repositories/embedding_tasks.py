"""
Celery tasks for vector embedding generation — Phase 2.3.

Tasks:
  generate_repo_embedding          — Embed a single Repository
  generate_pending_repo_embeddings — Batch-queue unembedded Repositories
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


def _build_repo_text(repo) -> str:
    """Build the text to embed for a Repository."""
    parts = []
    if repo.name:
        parts.append(repo.name)
    if repo.description:
        parts.append(repo.description)
    if repo.language:
        parts.append(repo.language)
    if repo.topics:
        parts.append(" ".join(repo.topics[:10]))
    if repo.readme_summary:
        parts.append(repo.readme_summary[:2000])
    return " ".join(parts)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="embeddings",
    name="apps.repositories.embedding_tasks.generate_repo_embedding",
)
def generate_repo_embedding(self, repo_id: str) -> Dict:
    """
    Generate and store a vector embedding for a single Repository.

    Args:
        repo_id: UUID string of the Repository to embed.
    """
    task_id = self.request.id
    logger.info("[%s] Generating embedding for repo: %s", task_id, repo_id)
    start_time = time.time()

    try:
        from apps.repositories.models import Repository  # noqa: PLC0415

        try:
            repo = Repository.objects.get(pk=repo_id)
        except Repository.DoesNotExist:
            logger.error("[%s] Repository %s not found.", task_id, repo_id)
            return {"status": "error", "reason": "not_found", "repo_id": repo_id}

        text = _build_repo_text(repo)
        if not text.strip():
            return {"status": "skipped", "reason": "no_content", "repo_id": repo_id}

        embedder = _get_embedder()
        vector = embedder.embed(text)

        repo.embedding = vector
        repo.save(update_fields=["embedding"])

        elapsed = round(time.time() - start_time, 2)
        logger.info("[%s] Embedded repo %s in %.2fs", task_id, repo_id, elapsed)
        return {
            "status": "success",
            "repo_id": repo_id,
            "dimensions": len(vector),
            "elapsed_seconds": elapsed,
        }

    except Exception as exc:
        logger.error("[%s] Error embedding repo %s: %s", task_id, repo_id, exc)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(
    bind=True,
    max_retries=1,
    queue="embeddings",
    name="apps.repositories.embedding_tasks.generate_pending_repo_embeddings",
)
def generate_pending_repo_embeddings(self, batch_size: int = 100) -> Dict:
    """Queue embedding for Repositories without an embedding."""
    task_id = self.request.id
    try:
        from apps.repositories.models import Repository  # noqa: PLC0415

        pending_ids = list(
            Repository.objects.filter(embedding__isnull=True).values_list(
                "id", flat=True
            )[:batch_size]
        )
        for repo_id in pending_ids:
            generate_repo_embedding.delay(str(repo_id))

        logger.info("[%s] Queued %d repo embedding tasks.", task_id, len(pending_ids))
        return {"status": "success", "queued": len(pending_ids)}

    except Exception as exc:
        logger.error("[%s] generate_pending_repo_embeddings failed: %s", task_id, exc)
        raise self.retry(exc=exc, countdown=120)
