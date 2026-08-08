"""
backend.apps.repositories.reembed_tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Celery task to re-embed all repositories with the new BAAI/bge-large-en-v1.5 model.

TASK-005-B3
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="repositories.reembed_all_repos", max_retries=3)
def reembed_all_repos(self, batch_size: int = 32) -> dict:
    """Re-embed all repositories using the current embedding model (1024 dims)."""
    import os

    import httpx
    from apps.repositories.models import Repository

    AI_ENGINE_URL = os.environ.get("AI_ENGINE_URL", "http://localhost:8001")
    repos = (
        Repository.objects.filter(description__isnull=False)
        .exclude(description="")
        .order_by("id")
    )
    total = repos.count()
    embedded = 0
    skipped = 0

    logger.info("reembed_all_repos: starting — total=%d", total)

    for i in range(0, total, batch_size):
        batch = list(repos[i : i + batch_size])
        texts, valid = [], []
        for repo in batch:
            text = f"{repo.name or ''} {repo.description or ''}"[:8192].strip()
            if text:
                texts.append(text)
                valid.append(repo)
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
            for repo, embedding in zip(valid, embeddings):
                repo.embedding = embedding
            Repository.objects.bulk_update(valid, ["embedding"])
            embedded += len(valid)
            logger.info("reembed_all_repos: %d/%d done", i + len(batch), total)
        except Exception as exc:
            logger.error("reembed_all_repos: batch %d failed: %s", i, exc)

    logger.info(
        "reembed_all_repos: complete — embedded=%d skipped=%d", embedded, skipped
    )
    return {"total": total, "embedded": embedded, "skipped": skipped}
