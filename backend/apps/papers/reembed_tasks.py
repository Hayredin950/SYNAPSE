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
    from apps.papers.models import ResearchPaper

    from ai_engine.embeddings import embed_batch

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
            embeddings = embed_batch(texts)
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
