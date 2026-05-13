from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Dict, List, Tuple

from apps.articles.models import Article
from apps.core.models import UserActivity
from apps.papers.models import ResearchPaper
from apps.repositories.models import Repository

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

WEIGHTS = {
    "view": 1.0,
    "bookmark": 3.0,
    "unbookmark": -1.5,  # slight negative impact
    "like": 2.0,
}


def _accumulate_scores(
    since, limit_per_type: int = 20
) -> Dict[str, List[Tuple[str, float]]]:
    """
    Return a mapping of model label -> list of (object_id, score) tuples sorted by score desc.
    Only considers activities since the given datetime.
    """
    qs = (
        UserActivity.objects.filter(timestamp__gte=since)
        .exclude(content_type__isnull=True)
        .exclude(object_id__isnull=True)
        .only("content_type_id", "object_id", "interaction_type")
    )

    scores: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for act in qs.iterator():
        weight = WEIGHTS.get(act.interaction_type, 0.0)
        if weight == 0.0:
            continue
        model_label = act.content_type.model
        scores[model_label][str(act.object_id)] += weight

    ranked: Dict[str, List[Tuple[str, float]]] = {}
    for model_label, id_map in scores.items():
        items = list(id_map.items())
        items.sort(key=lambda x: x[1], reverse=True)
        ranked[model_label] = items[:limit_per_type]

    return ranked


def get_trending(limit_per_type: int = 20, hours: int = 48):
    """
    Calculate trending items across Articles, ResearchPapers, and Repositories
    based on weighted interactions in the last N hours.
    """
    since = timezone.now() - timedelta(hours=hours)
    ranked = _accumulate_scores(since, limit_per_type=limit_per_type)

    # Fetch objects by type, preserve order according to ranked results
    def fetch(model_cls, pairs: List[Tuple[str, float]]):
        if not pairs:
            return []
        ids = [pid for pid, _ in pairs]
        objs = {str(o.id): o for o in model_cls.objects.filter(id__in=ids)}
        results = []
        for pid, score in pairs:
            obj = objs.get(pid)
            if obj:
                results.append((obj, score))
        return results

    article_pairs = ranked.get("article", [])
    paper_pairs = ranked.get("researchpaper", []) or ranked.get("paper", [])
    repo_pairs = ranked.get("repository", [])

    articles = fetch(Article, article_pairs)
    papers = fetch(ResearchPaper, paper_pairs)
    repos = fetch(Repository, repo_pairs)

    return {
        "articles": articles,
        "papers": papers,
        "repos": repos,
        "since": since,
    }
