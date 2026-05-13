from __future__ import annotations

from typing import List, Tuple

from apps.articles.models import Article
from apps.core.models import UserActivity
from apps.papers.models import ResearchPaper
from apps.repositories.models import Repository
from pgvector.django import CosineDistance


def _get_recent_vectors(
    user, max_items: int = 20
) -> tuple[list[list[float]], set, set, set]:
    """Collect embeddings from the user's most recent bookmark/view activities.

    Optimised: single DB query for activities + select_related for content_type,
    then batch-fetch embeddings per model type instead of N individual queries.
    """
    activities = list(
        UserActivity.objects.filter(
            user=user, interaction_type__in=["bookmark", "view"]
        )
        .select_related("content_type")  # eliminates N content_type lookups
        .order_by("-timestamp")[:max_items]
    )

    # Group object_ids by model to do 3 batch queries instead of N individual ones
    article_ids: list = []
    paper_ids: list = []
    repo_ids: list = []

    for act in activities:
        if not act.content_type_id or not act.object_id:
            continue
        model = act.content_type.model
        if model == "article":
            article_ids.append(act.object_id)
        elif model in ("researchpaper", "paper", "research_paper"):
            paper_ids.append(act.object_id)
        elif model == "repository":
            repo_ids.append(act.object_id)

    vectors: list[list[float]] = []
    seen_articles: set = set()
    seen_papers: set = set()
    seen_repos: set = set()

    # Batch fetch — 3 queries max instead of up to 20
    if article_ids:
        for obj in Article.objects.filter(id__in=article_ids).only("id", "embedding"):
            if obj.embedding:
                vectors.append(list(obj.embedding))
                seen_articles.add(obj.id)

    if paper_ids:
        for obj in ResearchPaper.objects.filter(id__in=paper_ids).only(
            "id", "embedding"
        ):
            if obj.embedding:
                vectors.append(list(obj.embedding))
                seen_papers.add(obj.id)

    if repo_ids:
        for obj in Repository.objects.filter(id__in=repo_ids).only("id", "embedding"):
            if obj.embedding:
                vectors.append(list(obj.embedding))
                seen_repos.add(obj.id)

    return vectors, seen_articles, seen_papers, seen_repos


def _mean_vector(vectors: list[list[float]]) -> list[float] | None:
    if not vectors:
        return None
    dim = len(vectors[0])
    acc = [0.0] * dim
    count = 0
    for v in vectors:
        if not v or len(v) != dim:
            continue
        count += 1
        for i, val in enumerate(v):
            acc[i] += float(val)
    if count == 0:
        return None
    return [x / count for x in acc]


def recommend_for_user(user, limit: int = 12, offset: int = 0) -> dict:
    """
    Content-based recommendations using a single 'User Interest Vector'.
    Steps:
      - Gather recent bookmark/view embeddings (last 20)
      - Compute the mean vector
      - Query each table with a single cosine similarity search
      - Exclude already seen items, apply offset/limit
    """
    results = {"articles": [], "papers": [], "repos": []}

    if not user or not user.is_authenticated:
        return results

    vectors, seen_articles, seen_papers, seen_repos = _get_recent_vectors(
        user, max_items=20
    )
    user_vec = _mean_vector(vectors)
    if not user_vec:
        return results

    # Articles
    art_qs = (
        Article.objects.filter(embedding__isnull=False)
        .exclude(id__in=list(seen_articles))
        .annotate(similarity=CosineDistance("embedding", user_vec))
        .order_by("similarity")
    )
    results["articles"] = list(art_qs[offset : offset + limit])

    # Papers
    pap_qs = (
        ResearchPaper.objects.filter(embedding__isnull=False)
        .exclude(id__in=list(seen_papers))
        .annotate(similarity=CosineDistance("embedding", user_vec))
        .order_by("similarity")
    )
    results["papers"] = list(pap_qs[offset : offset + limit])

    # Repositories
    rep_qs = (
        Repository.objects.filter(embedding__isnull=False)
        .exclude(id__in=list(seen_repos))
        .annotate(similarity=CosineDistance("embedding", user_vec))
        .order_by("similarity")
    )
    results["repos"] = list(rep_qs[offset : offset + limit])

    return results
