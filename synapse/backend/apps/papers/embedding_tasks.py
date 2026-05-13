"""
Celery tasks for vector embedding generation — Phase 2.3.

Tasks:
  generate_paper_embedding          — Embed a single ResearchPaper
  generate_pending_paper_embeddings — Batch-queue unembedded ResearchPapers
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


def _build_paper_text(paper) -> str:
    """Build the text to embed for a ResearchPaper."""
    parts = []
    if paper.title:
        parts.append(paper.title)
    if paper.abstract:
        parts.append(paper.abstract[:3000])
    if paper.categories:
        parts.append(" ".join(paper.categories[:5]))
    if paper.key_contributions:
        parts.append(paper.key_contributions[:500])
    return " ".join(parts)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="embeddings",
    name="apps.papers.embedding_tasks.generate_paper_embedding",
)
def generate_paper_embedding(self, paper_id: str) -> Dict:
    """
    Generate and store a vector embedding for a single ResearchPaper.

    Args:
        paper_id: UUID string of the ResearchPaper to embed.
    """
    task_id = self.request.id
    logger.info("[%s] Generating embedding for paper: %s", task_id, paper_id)
    start_time = time.time()

    try:
        from apps.papers.models import ResearchPaper  # noqa: PLC0415

        try:
            paper = ResearchPaper.objects.get(pk=paper_id)
        except ResearchPaper.DoesNotExist:
            logger.error("[%s] Paper %s not found.", task_id, paper_id)
            return {"status": "error", "reason": "not_found", "paper_id": paper_id}

        text = _build_paper_text(paper)
        if not text.strip():
            return {"status": "skipped", "reason": "no_content", "paper_id": paper_id}

        embedder = _get_embedder()
        vector = embedder.embed(text)

        paper.embedding = vector
        paper.save(update_fields=["embedding", "updated_at"])

        elapsed = round(time.time() - start_time, 2)
        logger.info("[%s] Embedded paper %s in %.2fs", task_id, paper_id, elapsed)
        return {
            "status": "success",
            "paper_id": paper_id,
            "dimensions": len(vector),
            "elapsed_seconds": elapsed,
        }

    except Exception as exc:
        logger.error("[%s] Error embedding paper %s: %s", task_id, paper_id, exc)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(
    bind=True,
    max_retries=1,
    queue="embeddings",
    name="apps.papers.embedding_tasks.generate_pending_paper_embeddings",
)
def generate_pending_paper_embeddings(self, batch_size: int = 100) -> Dict:
    """Queue embedding for ResearchPapers without an embedding."""
    task_id = self.request.id
    try:
        from apps.papers.models import ResearchPaper  # noqa: PLC0415

        pending_ids = list(
            ResearchPaper.objects.filter(embedding__isnull=True).values_list(
                "id", flat=True
            )[:batch_size]
        )
        for paper_id in pending_ids:
            generate_paper_embedding.delay(str(paper_id))

        logger.info("[%s] Queued %d paper embedding tasks.", task_id, len(pending_ids))
        return {"status": "success", "queued": len(pending_ids)}

    except Exception as exc:
        logger.error("[%s] generate_pending_paper_embeddings failed: %s", task_id, exc)
        raise self.retry(exc=exc, countdown=120)
