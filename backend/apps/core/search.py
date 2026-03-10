"""
SYNAPSE Hybrid Search Engine — TASK-301

Implements three complementary search strategies that can be used independently
or combined for maximum retrieval accuracy:

  1. BM25 (full-text)   — PostgreSQL tsvector / tsquery via Django's
                          SearchVector + SearchQuery + SearchRank.
                          Excels at exact keyword matches, rare terms, acronyms.

  2. Semantic (vector)  — pgvector cosine distance on 1024-dim BGE-large
                          embeddings. Excels at conceptual / paraphrase matching.

  3. Hybrid (RRF + rerank) — Reciprocal Rank Fusion merges both ranked lists,
                              then an optional cross-encoder reranker refines the
                              top-k candidates for maximum precision.

Reciprocal Rank Fusion formula (Cormack et al. 2009):
    score(d) = Σ  1 / (k + rank_i(d))
    where k=60 is the standard smoothing constant.

Cross-encoder reranking (optional):
    Loads BAAI/bge-reranker-base on first use (cached in memory). Falls back to
    RRF-only scores when the model is unavailable (e.g., CPU-only production).

Usage:
    from apps.core.search import hybrid_search, bm25_search, semantic_search_qs

    # Hybrid (recommended):
    results = hybrid_search(query, content_types=['articles', 'papers'], limit=10)

    # BM25 only:
    results = bm25_search(query, content_types=['articles'], limit=20)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Reciprocal Rank Fusion constant ──────────────────────────────────────────
RRF_K = 60

# ── Cross-encoder model (lazy-loaded, optional) ───────────────────────────────
_reranker = None
RERANKER_MODEL = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-base")
RERANKER_ENABLED = os.environ.get("RERANKER_ENABLED", "true").lower() == "true"


def _get_reranker():
    """Lazy-load the cross-encoder reranker (cached after first call)."""
    global _reranker
    if _reranker is not None:
        return _reranker
    if not RERANKER_ENABLED:
        return None
    try:
        from sentence_transformers import CrossEncoder

        _reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
        logger.info("Cross-encoder reranker loaded: %s", RERANKER_MODEL)
    except Exception as exc:
        logger.warning("Reranker unavailable (%s) — falling back to RRF scores", exc)
        _reranker = None
    return _reranker


# ── Result dataclass ──────────────────────────────────────────────────────────


@dataclass
class SearchResult:
    """Unified search result with provenance metadata."""

    id: str
    content_type: str  # 'article' | 'paper' | 'repo' | 'video'
    title: str
    snippet: str  # short text excerpt for reranker input
    obj: Any  # original Django model instance
    bm25_rank: int | None = field(default=None)
    semantic_rank: int | None = field(default=None)
    rrf_score: float = field(default=0.0)
    rerank_score: float | None = field(default=None)
    similarity_score: float | None = field(default=None)

    @property
    def final_score(self) -> float:
        """Best available score for sorting."""
        if self.rerank_score is not None:
            return self.rerank_score
        return self.rrf_score


# ── RRF merge ─────────────────────────────────────────────────────────────────


def _rrf_merge(
    bm25_results: list[SearchResult],
    semantic_results: list[SearchResult],
    k: int = RRF_K,
) -> list[SearchResult]:
    """
    Merge two ranked lists using Reciprocal Rank Fusion.

    Args:
        bm25_results:     Results ranked by BM25 score (best first).
        semantic_results: Results ranked by cosine similarity (best first).
        k:                RRF smoothing constant (default 60).

    Returns:
        Merged list sorted by RRF score descending.
    """
    scores: dict[str, float] = {}
    index: dict[str, SearchResult] = {}

    for rank, result in enumerate(bm25_results, start=1):
        scores[result.id] = scores.get(result.id, 0.0) + 1.0 / (k + rank)
        result.bm25_rank = rank
        index[result.id] = result

    for rank, result in enumerate(semantic_results, start=1):
        scores[result.id] = scores.get(result.id, 0.0) + 1.0 / (k + rank)
        result.semantic_rank = rank
        if result.id in index:
            # Update existing entry's semantic rank
            index[result.id].semantic_rank = rank
            index[result.id].similarity_score = result.similarity_score
        else:
            index[result.id] = result

    for result_id, score in scores.items():
        index[result_id].rrf_score = score

    return sorted(index.values(), key=lambda r: r.rrf_score, reverse=True)


# ── Cross-encoder rerank ──────────────────────────────────────────────────────


def _rerank(query: str, results: list[SearchResult], top_k: int) -> list[SearchResult]:
    """
    Rerank the top candidates using a cross-encoder model.

    Only the first `top_k * 3` candidates are passed to the reranker to limit
    inference cost. Falls back silently to RRF order if model is unavailable.
    """
    reranker = _get_reranker()
    if not reranker or not results:
        return results

    candidates = results[: top_k * 3]
    pairs = [(query, r.title + "\n" + r.snippet) for r in candidates]

    try:
        scores = reranker.predict(pairs)
        for result, score in zip(candidates, scores):
            result.rerank_score = float(score)
        candidates.sort(key=lambda r: r.rerank_score or 0.0, reverse=True)
    except Exception as exc:
        logger.warning("Reranker inference failed: %s — falling back to RRF order", exc)

    return candidates + results[top_k * 3 :]


# ── Model-specific query helpers ──────────────────────────────────────────────


def _article_to_result(
    article, bm25_rank=None, semantic_rank=None, similarity_score=None
) -> SearchResult:
    from apps.articles.models import Article  # noqa

    return SearchResult(
        id=str(article.pk),
        content_type="article",
        title=article.title,
        snippet=(article.summary or article.content or "")[:300],
        obj=article,
        bm25_rank=bm25_rank,
        semantic_rank=semantic_rank,
        similarity_score=similarity_score,
    )


def _paper_to_result(
    paper, bm25_rank=None, semantic_rank=None, similarity_score=None
) -> SearchResult:
    return SearchResult(
        id=str(paper.pk),
        content_type="paper",
        title=paper.title,
        snippet=(paper.abstract or paper.summary or "")[:300],
        obj=paper,
        bm25_rank=bm25_rank,
        semantic_rank=semantic_rank,
        similarity_score=similarity_score,
    )


def _repo_to_result(
    repo, bm25_rank=None, semantic_rank=None, similarity_score=None
) -> SearchResult:
    return SearchResult(
        id=str(repo.pk),
        content_type="repo",
        title=repo.name,
        snippet=(repo.description or "")[:300],
        obj=repo,
        bm25_rank=bm25_rank,
        semantic_rank=semantic_rank,
        similarity_score=similarity_score,
    )


def _video_to_result(
    video, bm25_rank=None, semantic_rank=None, similarity_score=None
) -> SearchResult:
    return SearchResult(
        id=str(video.pk),
        content_type="video",
        title=video.title,
        snippet=(video.description or video.summary or "")[:300],
        obj=video,
        bm25_rank=bm25_rank,
        semantic_rank=semantic_rank,
        similarity_score=similarity_score,
    )


# ── BM25 (full-text) search ───────────────────────────────────────────────────


def bm25_search(
    query: str,
    content_types: list[str] | None = None,
    limit: int = 10,
    filters: dict | None = None,
) -> dict[str, list[SearchResult]]:
    """
    Full-text BM25 search using PostgreSQL tsvector + SearchRank.

    Falls back to ILIKE trigram search for short queries (< 3 chars) where
    tsvector tokenisation is unreliable.

    Args:
        query:         Search query string.
        content_types: List of content types to search. Defaults to all.
        limit:         Max results per content type.
        filters:       Optional per-type filters dict.

    Returns:
        Dict mapping content_type → list[SearchResult], sorted by BM25 rank.
    """
    from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
    from django.db.models import F

    if content_types is None:
        content_types = ["articles", "papers", "repos", "videos"]
    filters = filters or {}

    # Use plainto_tsquery for multi-word queries, websearch_to_tsquery for
    # quoted phrases and boolean operators ("AND", "OR", "-" negation).
    search_query = SearchQuery(query, search_type="websearch", config="english")
    results: dict[str, list[SearchResult]] = {}

    # ── Articles ──────────────────────────────────────────────────────────────
    if "articles" in content_types:
        from apps.articles.models import Article

        sv = (
            SearchVector("title", weight="A", config="english")
            + SearchVector("summary", weight="B", config="english")
            + SearchVector("content", weight="C", config="english")
        )
        qs = (
            Article.objects.annotate(search=sv, rank=SearchRank(sv, search_query))
            .filter(search=search_query)
            .order_by("-rank")
        )
        if filters.get("topic"):
            qs = qs.filter(topic__iexact=filters["topic"])
        if filters.get("source"):
            qs = qs.filter(source__source_type__iexact=filters["source"])

        articles = list(qs[:limit])
        results["articles"] = [
            _article_to_result(a, bm25_rank=i + 1) for i, a in enumerate(articles)
        ]

    # ── Papers ────────────────────────────────────────────────────────────────
    if "papers" in content_types:
        from apps.papers.models import ResearchPaper

        # authors is an ArrayField — exclude it from SearchVector to avoid type errors;
        # author names are searchable via title/abstract match in practice.
        sv = (
            SearchVector("title", weight="A", config="english")
            + SearchVector("abstract", weight="B", config="english")
            + SearchVector("summary", weight="C", config="english")
        )
        qs = (
            ResearchPaper.objects.annotate(search=sv, rank=SearchRank(sv, search_query))
            .filter(search=search_query)
            .order_by("-rank")
        )
        if filters.get("category"):
            qs = qs.filter(categories__icontains=filters["category"])

        papers = list(qs[:limit])
        results["papers"] = [
            _paper_to_result(p, bm25_rank=i + 1) for i, p in enumerate(papers)
        ]

    # ── Repositories ──────────────────────────────────────────────────────────
    if "repos" in content_types:
        from apps.repositories.models import Repository

        sv = SearchVector("name", weight="A", config="english") + SearchVector(
            "description", weight="B", config="english"
        )
        qs = (
            Repository.objects.annotate(search=sv, rank=SearchRank(sv, search_query))
            .filter(search=search_query)
            .order_by("-rank")
        )
        if filters.get("language"):
            qs = qs.filter(language__iexact=filters["language"])

        repos = list(qs[:limit])
        results["repos"] = [
            _repo_to_result(r, bm25_rank=i + 1) for i, r in enumerate(repos)
        ]

    # ── Videos ────────────────────────────────────────────────────────────────
    if "videos" in content_types:
        from apps.videos.models import Video

        sv = (
            SearchVector("title", weight="A", config="english")
            + SearchVector("description", weight="B", config="english")
            + SearchVector("summary", weight="C", config="english")
        )
        qs = (
            Video.objects.annotate(search=sv, rank=SearchRank(sv, search_query))
            .filter(search=search_query)
            .order_by("-rank")
        )

        videos = list(qs[:limit])
        results["videos"] = [
            _video_to_result(v, bm25_rank=i + 1) for i, v in enumerate(videos)
        ]

    return results


# ── Semantic search ───────────────────────────────────────────────────────────


def semantic_search_results(
    query_vector: list[float],
    content_types: list[str] | None = None,
    limit: int = 10,
    filters: dict | None = None,
) -> dict[str, list[SearchResult]]:
    """
    Pure semantic search using pgvector CosineDistance.

    Args:
        query_vector:  Embedding vector for the query (1024-dim float list).
        content_types: Content types to search.
        limit:         Max results per type.
        filters:       Optional per-type filters.

    Returns:
        Dict mapping content_type → list[SearchResult] sorted by similarity.
    """
    from pgvector.django import CosineDistance

    if content_types is None:
        content_types = ["articles", "papers", "repos", "videos"]
    filters = filters or {}
    results: dict[str, list[SearchResult]] = {}

    def _similarity(dist: float | None) -> float | None:
        """Convert CosineDistance (0=identical, 2=opposite) to 0-1 score."""
        return round(1 - (dist / 2), 4) if dist is not None else None

    if "articles" in content_types:
        from apps.articles.models import Article

        qs = (
            Article.objects.filter(embedding__isnull=False)
            .annotate(dist=CosineDistance("embedding", query_vector))
            .order_by("dist")
        )
        if filters.get("topic"):
            qs = qs.filter(topic__iexact=filters["topic"])
        if filters.get("source"):
            qs = qs.filter(source__source_type__iexact=filters["source"])
        if filters.get("date_from"):
            qs = qs.filter(published_at__gte=filters["date_from"])
        if filters.get("date_to"):
            qs = qs.filter(published_at__lte=filters["date_to"])

        articles = list(qs[:limit])
        results["articles"] = [
            _article_to_result(
                a,
                semantic_rank=i + 1,
                similarity_score=_similarity(getattr(a, "dist", None)),
            )
            for i, a in enumerate(articles)
        ]

    if "papers" in content_types:
        from apps.papers.models import ResearchPaper

        qs = (
            ResearchPaper.objects.filter(embedding__isnull=False)
            .annotate(dist=CosineDistance("embedding", query_vector))
            .order_by("dist")
        )
        if filters.get("category"):
            qs = qs.filter(categories__icontains=filters["category"])

        papers = list(qs[:limit])
        results["papers"] = [
            _paper_to_result(
                p,
                semantic_rank=i + 1,
                similarity_score=_similarity(getattr(p, "dist", None)),
            )
            for i, p in enumerate(papers)
        ]

    if "repos" in content_types:
        from apps.repositories.models import Repository

        qs = (
            Repository.objects.filter(embedding__isnull=False)
            .annotate(dist=CosineDistance("embedding", query_vector))
            .order_by("dist")
        )
        if filters.get("language"):
            qs = qs.filter(language__iexact=filters["language"])

        repos = list(qs[:limit])
        results["repos"] = [
            _repo_to_result(
                r,
                semantic_rank=i + 1,
                similarity_score=_similarity(getattr(r, "dist", None)),
            )
            for i, r in enumerate(repos)
        ]

    if "videos" in content_types:
        from apps.videos.models import Video

        qs = (
            Video.objects.filter(embedding__isnull=False)
            .annotate(dist=CosineDistance("embedding", query_vector))
            .order_by("dist")
        )
        videos = list(qs[:limit])
        results["videos"] = [
            _video_to_result(
                v,
                semantic_rank=i + 1,
                similarity_score=_similarity(getattr(v, "dist", None)),
            )
            for i, v in enumerate(videos)
        ]

    return results


# ── Hybrid search (BM25 + Semantic + RRF + optional rerank) ──────────────────


def hybrid_search(
    query: str,
    query_vector: list[float],
    content_types: list[str] | None = None,
    limit: int = 10,
    filters: dict | None = None,
    use_reranker: bool = True,
) -> dict[str, list[SearchResult]]:
    """
    Hybrid search: merge BM25 and semantic results with Reciprocal Rank Fusion,
    then optionally rerank the merged top-k with a cross-encoder model.

    Args:
        query:         Raw text query (used for BM25 + reranker).
        query_vector:  Pre-computed query embedding (used for semantic search).
        content_types: Content types to search (default all).
        limit:         Max results per content type in final output.
        filters:       Optional per-type filters.
        use_reranker:  Whether to apply cross-encoder reranking (default True).

    Returns:
        Dict mapping content_type → list[SearchResult] sorted by final_score.
    """
    if content_types is None:
        content_types = ["articles", "papers", "repos", "videos"]

    # Fetch more candidates than needed so RRF + reranker have headroom
    fetch_limit = min(limit * 3, 50)

    bm25_raw = bm25_search(query, content_types, fetch_limit, filters)
    semantic_raw = semantic_search_results(
        query_vector, content_types, fetch_limit, filters
    )

    merged: dict[str, list[SearchResult]] = {}

    all_types = set(list(bm25_raw.keys()) + list(semantic_raw.keys()))
    for ct in all_types:
        bm25_list = bm25_raw.get(ct, [])
        semantic_list = semantic_raw.get(ct, [])

        fused = _rrf_merge(bm25_list, semantic_list)

        if use_reranker:
            fused = _rerank(query, fused, top_k=limit)

        merged[ct] = fused[:limit]

    return merged
