"""
backend.apps.papers.reembed_tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Celery task to re-embed all research papers with the new BAAI/bge-large-en-v1.5 model.

TASK-005-B3
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="papers.reembed_all_papers", max_retries=3)
def reembed_all_papers(self, batch_size: int = 32) -> dict:
    """Re-embed all research papers using the current embedding model (1024 dims)."""
    import os

    import httpx
    from apps.papers.models import ResearchPaper

    AI_ENGINE_URL = os.environ.get("AI_ENGINE_URL", "http://localhost:8001")
    papers = (
        ResearchPaper.objects.filter(abstract__isnull=False)
        .exclude(abstract="")
        .order_by("id")
    )
    total = papers.count()
    embedded = 0
    skipped = 0

    logger.info("reembed_all_papers: starting — total=%d", total)

    for i in range(0, total, batch_size):
        batch = list(papers[i : i + batch_size])
        texts, valid = [], []
        for paper in batch:
            text = f"{paper.title or ''} {paper.abstract or ''}"[:8192].strip()
            if text:
                texts.append(text)
                valid.append(paper)
            else:
                skipped += 1

        if not texts:
            continue

        try:
            resp = httpx.post(
                f"{AI_ENGINE_URL}/embeddings", json={"texts": texts}, timeout=120
            )
            resp.raise_for_status()
            embeddings = resp.json()["embeddings"]
            for paper, embedding in zip(valid, embeddings):
                paper.embedding = embedding
            ResearchPaper.objects.bulk_update(valid, ["embedding"])
            embedded += len(valid)
            logger.info("reembed_all_papers: %d/%d done", i + len(batch), total)
        except Exception as exc:
            logger.error("reembed_all_papers: batch %d failed: %s", i, exc)

    logger.info(
        "reembed_all_papers: complete — embedded=%d skipped=%d", embedded, skipped
    )
    return {"total": total, "embedded": embedded, "skipped": skipped}
