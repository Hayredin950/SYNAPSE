"""
backend.apps.core.semantic_cache
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Semantic response cache for LLM calls.

An exact-match cache is nearly useless for natural language — "what's new in
LLM agents?" and "latest news on LLM agents" are the same question with
different bytes. This cache embeds the prompt and looks for a previously
answered prompt whose vector is close enough, so paraphrases hit too.

That matters here because SYNAPSE is a trends/research app: many users ask
about the same handful of hot topics on the same day, and each miss costs a
full agent run (up to MAX_ITERATIONS upstream calls).

Cost of a lookup is one *local* embedding (free, no API) plus one indexed
pgvector query — far cheaper than the LLM call it avoids.

Usage:
    from apps.core.semantic_cache import lookup, store

    hit = lookup(prompt, scope="chat")
    if hit is not None:
        return hit
    answer = expensive_llm_call(prompt)
    store(prompt, answer, scope="chat")
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Cosine distance below which two prompts count as the same question.
# pgvector's <=> operator returns cosine DISTANCE (0 = identical).
# 0.05 ≈ 0.95 cosine similarity — deliberately strict, since serving the wrong
# cached answer is much worse than paying for one more LLM call.
_THRESHOLD = float(os.environ.get("SEMANTIC_CACHE_THRESHOLD", "0.05"))
_TTL_HOURS = int(os.environ.get("SEMANTIC_CACHE_TTL_HOURS", "24"))
_ENABLED = os.environ.get("SEMANTIC_CACHE", "1").lower() not in ("0", "false", "no")


def _embed(text: str) -> Optional[list]:
    """Embed a prompt locally. Returns None if the embedder is unavailable."""
    try:
        import sys

        root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        if root not in sys.path:
            sys.path.insert(0, root)
        from ai_engine.embeddings import get_embedder  # noqa: PLC0415

        return get_embedder().embed_query(text)
    except Exception as exc:
        logger.debug("semantic_cache: embedder unavailable (%s)", exc)
        return None


def lookup(prompt: str, scope: str = "default") -> Optional[str]:
    """
    Return a cached response for a semantically equivalent prompt, or None.

    `scope` partitions the cache so a chat answer is never served to an agent
    request (and vice versa) — same words, different expected output shape.

    Never raises: a cache failure must degrade to a normal LLM call.
    """
    if not _ENABLED or not prompt or not prompt.strip():
        return None

    try:
        from datetime import timedelta

        from django.utils import timezone

        from apps.core.models import SemanticCacheEntry  # noqa: PLC0415

        vector = _embed(prompt)
        if vector is None:
            return None

        cutoff = timezone.now() - timedelta(hours=_TTL_HOURS)

        from pgvector.django import CosineDistance  # noqa: PLC0415

        hit = (
            SemanticCacheEntry.objects.filter(scope=scope, created_at__gte=cutoff)
            .annotate(distance=CosineDistance("prompt_embedding", vector))
            .filter(distance__lt=_THRESHOLD)
            .order_by("distance")
            .first()
        )

        if hit is None:
            return None

        # Cheap popularity signal — useful for deciding what to pre-warm.
        SemanticCacheEntry.objects.filter(pk=hit.pk).update(hits=hit.hits + 1)
        logger.info(
            "semantic_cache HIT scope=%s distance=%.4f hits=%d",
            scope,
            hit.distance,
            hit.hits + 1,
        )
        return hit.response

    except Exception as exc:
        logger.debug("semantic_cache lookup failed: %s", exc)
        return None


def store(prompt: str, response: str, scope: str = "default") -> None:
    """Cache a response. Never raises."""
    if not _ENABLED or not prompt or not prompt.strip() or not response:
        return

    try:
        from apps.core.models import SemanticCacheEntry  # noqa: PLC0415

        vector = _embed(prompt)
        if vector is None:
            return

        SemanticCacheEntry.objects.create(
            scope=scope,
            prompt=prompt[:4000],
            prompt_embedding=vector,
            response=response,
        )
        logger.debug("semantic_cache STORE scope=%s", scope)

    except Exception as exc:
        logger.debug("semantic_cache store failed: %s", exc)


def purge_expired() -> int:
    """Delete entries past their TTL. Returns the number removed."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.models import SemanticCacheEntry  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(hours=_TTL_HOURS)
    deleted, _ = SemanticCacheEntry.objects.filter(created_at__lt=cutoff).delete()
    if deleted:
        logger.info("semantic_cache purged %d expired entries", deleted)
    return deleted
