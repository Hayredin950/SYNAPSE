import os

import redis
from apps.articles.models import Article
from apps.articles.serializers import ArticleListSerializer
from apps.papers.models import ResearchPaper
from apps.papers.serializers import ResearchPaperSerializer
from apps.repositories.models import Repository
from apps.repositories.serializers import RepositorySerializer

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .audit import AuditLog
from .models import (
    Collection,
    DailyBriefing,
    KnowledgeEdge,
    KnowledgeNode,
    UserActivity,
    UserBookmark,
)
from .recommendations import recommend_for_user
from .serializers import (
    BookmarkSerializer,
    CollectionListSerializer,
    CollectionSerializer,
)
from .trending import get_trending


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    health = {"status": "healthy", "services": {}}
    try:
        connection.ensure_connection()
        health["services"]["database"] = "ok"
    except Exception:
        health["services"]["database"] = "error"
        health["status"] = "degraded"
    try:
        r = redis.from_url(os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"))
        r.ping()
        health["services"]["redis"] = "ok"
    except Exception:
        health["services"]["redis"] = "error"
        health["status"] = "degraded"
    return Response({"success": True, "data": health})


@api_view(["GET"])
@permission_classes([AllowAny])
def global_search(request):
    """Global full-text search across articles, repositories, research papers, and videos."""
    query = request.GET.get("q", "").strip()
    content_types = request.GET.get("types", "articles,repos,papers,videos").split(",")
    limit = min(int(request.GET.get("limit", 10)), 50)

    if not query or len(query) < 2:
        return Response(
            {
                "success": False,
                "error": {"message": "Query must be at least 2 characters"},
            },
            status=400,
        )

    results = {}

    if "articles" in content_types:
        articles = (
            Article.objects.filter(
                Q(title__icontains=query)
                | Q(summary__icontains=query)
                | Q(author__icontains=query)
                | Q(topic__icontains=query)
            )
            .select_related("source")
            .order_by("-trending_score", "-published_at")[:limit]
        )
        results["articles"] = ArticleListSerializer(articles, many=True).data

    if "repos" in content_types:
        repos = Repository.objects.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(owner__icontains=query)
            | Q(language__icontains=query)
        ).order_by("-stars")[:limit]
        results["repos"] = RepositorySerializer(repos, many=True).data

    if "papers" in content_types:
        papers = ResearchPaper.objects.filter(
            Q(title__icontains=query)
            | Q(abstract__icontains=query)
            | Q(summary__icontains=query)
        ).order_by("-citation_count", "-published_date")[:limit]
        results["papers"] = ResearchPaperSerializer(papers, many=True).data

    if "videos" in content_types:
        from apps.videos.models import Video  # noqa: PLC0415
        from apps.videos.serializers import VideoSerializer  # noqa: PLC0415

        videos = Video.objects.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(channel_name__icontains=query)
            | Q(summary__icontains=query)
        ).order_by("-view_count")[:limit]
        results["videos"] = VideoSerializer(videos, many=True).data

    total = sum(len(v) for v in results.values())
    # Log search activity (Phase 2.4)
    try:
        if request.user and request.user.is_authenticated:
            UserActivity.objects.create(
                user=request.user, interaction_type="search", metadata={"query": query}
            )
    except Exception:
        pass
    return Response(
        {
            "success": True,
            "data": results,
            "meta": {"query": query, "total": total, "limit": limit},
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def bm25_search_view(request):
    """
    POST /api/v1/search/bm25/

    Full-text BM25 search via PostgreSQL tsvector / tsquery + SearchRank.
    Best for exact keyword matches, acronyms, and rare terms.

    Request body (JSON):
        query        (str, required)
        limit        (int, optional)    default 10, max 50
        content_types (list, optional)  default all
        filters      (dict, optional)

    Response (200):
        { "success": true, "data": { "articles": [...], ... },
          "meta": { "query": "...", "mode": "bm25", ... } }
    """
    import time as _time

    from apps.articles.serializers import ArticleListSerializer
    from apps.core.search import bm25_search
    from apps.papers.serializers import ResearchPaperSerializer
    from apps.repositories.serializers import RepositorySerializer

    query = request.data.get("query", "").strip()
    if not query:
        return Response(
            {"success": False, "error": {"message": 'Field "query" is required.'}},
            status=422,
        )

    limit = min(int(request.data.get("limit", 10)), 50)
    content_types = request.data.get(
        "content_types", ["articles", "papers", "repos", "videos"]
    )
    filters = request.data.get("filters", {})
    start = _time.time()

    raw = bm25_search(query, content_types, limit, filters)

    data = {}
    serializer_map = {
        "articles": ArticleListSerializer,
        "papers": ResearchPaperSerializer,
        "repos": RepositorySerializer,
    }
    for ct, results in raw.items():
        Ser = serializer_map.get(ct)
        if Ser:
            serialized = Ser([r.obj for r in results], many=True).data
            for i, item in enumerate(serialized):
                item["bm25_rank"] = results[i].bm25_rank
            data[ct] = serialized
        else:
            # videos — inline serialization
            data[ct] = [
                {"id": str(r.obj.pk), "title": r.obj.title, "bm25_rank": r.bm25_rank}
                for r in results
            ]

    total = sum(len(v) for v in data.values())
    elapsed_ms = round((_time.time() - start) * 1000)

    # Log search activity
    try:
        if request.user and request.user.is_authenticated:
            UserActivity.objects.create(
                user=request.user,
                interaction_type="search",
                metadata={"query": query, "mode": "bm25"},
            )
    except Exception:
        pass

    return Response(
        {
            "success": True,
            "data": data,
            "meta": {
                "query": query,
                "mode": "bm25",
                "limit": limit,
                "total": total,
                "content_types": content_types,
                "execution_time_ms": elapsed_ms,
            },
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def hybrid_search_view(request):
    """
    POST /api/v1/search/hybrid/

    Hybrid search: BM25 + semantic merged via Reciprocal Rank Fusion, with
    optional cross-encoder reranking. Recommended default for best quality.

    Request body (JSON):
        query         (str, required)
        limit         (int, optional)     default 10, max 50
        content_types (list, optional)    default all
        filters       (dict, optional)
        use_reranker  (bool, optional)    default true

    Response (200):
        { "success": true, "data": { "articles": [...], ... },
          "meta": { "query": "...", "mode": "hybrid", "reranked": true, ... } }
    """
    import os
    import sys
    import time as _time

    from apps.articles.serializers import ArticleListSerializer
    from apps.core.search import hybrid_search
    from apps.papers.serializers import ResearchPaperSerializer
    from apps.repositories.serializers import RepositorySerializer

    query = request.data.get("query", "").strip()
    if not query:
        return Response(
            {"success": False, "error": {"message": 'Field "query" is required.'}},
            status=422,
        )

    limit = min(int(request.data.get("limit", 10)), 50)
    content_types = request.data.get(
        "content_types", ["articles", "papers", "repos", "videos"]
    )
    filters = request.data.get("filters", {})
    use_reranker = bool(request.data.get("use_reranker", True))
    start = _time.time()

    # ── Generate query embedding ──────────────────────────────────────────────
    try:
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from ai_engine.embeddings import embed_text

        query_vector = embed_text(query)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).error("Embedding generation failed: %s", exc)
        return Response(
            {
                "success": False,
                "error": {
                    "message": "Embedding service unavailable.",
                    "detail": str(exc),
                },
            },
            status=503,
        )

    raw = hybrid_search(
        query=query,
        query_vector=query_vector,
        content_types=content_types,
        limit=limit,
        filters=filters,
        use_reranker=use_reranker,
    )

    data = {}
    serializer_map = {
        "articles": ArticleListSerializer,
        "papers": ResearchPaperSerializer,
        "repos": RepositorySerializer,
    }
    for ct, results in raw.items():
        Ser = serializer_map.get(ct)
        if Ser:
            serialized = Ser([r.obj for r in results], many=True).data
            for i, item in enumerate(serialized):
                item["similarity_score"] = results[i].similarity_score
                item["bm25_rank"] = results[i].bm25_rank
                item["semantic_rank"] = results[i].semantic_rank
                item["rrf_score"] = round(results[i].rrf_score, 6)
                item["rerank_score"] = results[i].rerank_score
            data[ct] = serialized
        else:
            data[ct] = [
                {
                    "id": str(r.obj.pk),
                    "title": r.obj.title,
                    "similarity_score": r.similarity_score,
                    "rrf_score": round(r.rrf_score, 6),
                    "rerank_score": r.rerank_score,
                }
                for r in results
            ]

    total = sum(len(v) for v in data.values())
    elapsed_ms = round((_time.time() - start) * 1000)
    reranked = use_reranker and any(
        r.rerank_score is not None for results in raw.values() for r in results
    )

    # Log search activity
    try:
        if request.user and request.user.is_authenticated:
            UserActivity.objects.create(
                user=request.user,
                interaction_type="search",
                metadata={"query": query, "mode": "hybrid", "reranked": reranked},
            )
    except Exception:
        pass

    return Response(
        {
            "success": True,
            "data": data,
            "meta": {
                "query": query,
                "mode": "hybrid",
                "reranked": reranked,
                "limit": limit,
                "total": total,
                "content_types": content_types,
                "execution_time_ms": elapsed_ms,
            },
        }
    )


def _dist_to_similarity(dist) -> float | None:
    """Convert CosineDistance (0=identical, 2=opposite) to a 0–1 similarity score."""
    return round(1 - (dist / 2), 4) if dist is not None else None


def _annotate_similarity(objects: list, serialized: list) -> list:
    """Attach similarity_score to each serialized item in-place."""
    for i, item in enumerate(serialized):
        dist = getattr(objects[i], "similarity", None)
        item["similarity_score"] = _dist_to_similarity(dist)
    return serialized


def _vector_search(
    model_cls, serializer_cls, query_vector, limit: int, extra_filters: dict
):
    """
    QA-11: Shared helper for vector similarity search across any content model.

    Annotates queryset with CosineDistance, applies extra_filters, slices to
    `limit`, serializes, and attaches similarity_score to each result.
    """
    from pgvector.django import CosineDistance  # noqa: PLC0415

    qs = (
        model_cls.objects.filter(embedding__isnull=False)
        .annotate(similarity=CosineDistance("embedding", query_vector))
        .order_by("similarity")
    )
    for attr, value in extra_filters.items():
        if value:
            qs = qs.filter(**{attr: value})

    objects = list(qs[:limit])
    serialized = list(serializer_cls(objects, many=True).data)
    return _annotate_similarity(objects, serialized)


@api_view(["POST"])
@permission_classes([AllowAny])
def semantic_search(request):
    """
    POST /api/v1/search/semantic

    Perform semantic (vector) search across Articles, ResearchPapers,
    Repositories, Videos, and Tweets using pgvector cosine similarity.

    Request body (JSON):
        query         (str, required)  — Natural language search query.
        limit         (int, optional)  — Max results per content type (default 10, max 50).
        content_types (list, optional) — Which types to search. Defaults to all five.
        filters       (dict, optional) — Optional per-type filters.

    Response (200):
        {"success": true, "data": {...}, "meta": {...}}
    """
    import os
    import sys
    import time as _time

    query = request.data.get("query", "").strip()
    if not query:
        return Response(
            {"success": False, "error": {"message": 'Field "query" is required.'}},
            status=422,
        )

    limit = min(int(request.data.get("limit", 10)), 50)
    content_types = request.data.get(
        "content_types", ["articles", "papers", "repos", "videos", "tweets"]
    )
    filters = request.data.get("filters", {})
    start_time = _time.time()

    # ── 1. Generate query embedding ───────────────────────────────────────────
    try:
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from ai_engine.embeddings import embed_text  # noqa: PLC0415

        query_vector = embed_text(query)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).error("Embedding generation failed: %s", exc)
        return Response(
            {
                "success": False,
                "error": {
                    "message": "Embedding service unavailable.",
                    "detail": str(exc),
                },
            },
            status=503,
        )

    # ── 2. Search each content type via shared helper ─────────────────────────
    results: dict = {}

    if "articles" in content_types:
        from apps.articles.models import Article  # noqa: PLC0415
        from apps.articles.serializers import ArticleListSerializer  # noqa: PLC0415

        results["articles"] = _vector_search(
            Article,
            ArticleListSerializer,
            query_vector,
            limit,
            extra_filters={
                "topic__iexact": filters.get("topic"),
                "source__source_type__iexact": filters.get("source"),
                "published_at__gte": filters.get("date_from"),
                "published_at__lte": filters.get("date_to"),
            },
        )

    if "papers" in content_types:
        from apps.papers.models import ResearchPaper  # noqa: PLC0415
        from apps.papers.serializers import ResearchPaperSerializer  # noqa: PLC0415

        results["papers"] = _vector_search(
            ResearchPaper,
            ResearchPaperSerializer,
            query_vector,
            limit,
            extra_filters={
                "categories__icontains": filters.get("category"),
                "difficulty_level__iexact": filters.get("difficulty"),
            },
        )

    if "repos" in content_types:
        from apps.repositories.models import Repository  # noqa: PLC0415
        from apps.repositories.serializers import RepositorySerializer  # noqa: PLC0415

        results["repos"] = _vector_search(
            Repository,
            RepositorySerializer,
            query_vector,
            limit,
            extra_filters={"language__iexact": filters.get("language")},
        )

    if "videos" in content_types:
        from apps.videos.models import Video  # noqa: PLC0415
        from apps.videos.serializers import VideoSerializer  # noqa: PLC0415

        results["videos"] = _vector_search(
            Video,
            VideoSerializer,
            query_vector,
            limit,
            extra_filters={},
        )

    if "tweets" in content_types:
        from apps.tweets.models import Tweet  # noqa: PLC0415
        from apps.tweets.serializers import TweetListSerializer  # noqa: PLC0415

        results["tweets"] = _vector_search(
            Tweet,
            TweetListSerializer,
            query_vector,
            limit,
            extra_filters={"topic__iexact": filters.get("topic")},
        )

    # ── 3. Build response ─────────────────────────────────────────────────────
    total = sum(len(v) for v in results.values())
    elapsed_ms = round((_time.time() - start_time) * 1000)

    return Response(
        {
            "success": True,
            "data": results,
            "meta": {
                "query": query,
                "limit": limit,
                "total": total,
                "content_types": content_types,
                "execution_time_ms": elapsed_ms,
            },
        }
    )


class BookmarkListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all bookmarks for the current user."""
        content_type_filter = request.GET.get("type")
        bookmarks = UserBookmark.objects.filter(user=request.user).select_related(
            "content_type"
        )
        if content_type_filter:
            bookmarks = bookmarks.filter(content_type__model=content_type_filter)
        # Evaluate queryset once — avoids second COUNT(*) query
        bookmark_list = list(bookmarks)
        serializer = BookmarkSerializer(bookmark_list, many=True)
        return Response(
            {
                "success": True,
                "data": serializer.data,
                "meta": {"total": len(bookmark_list)},
            }
        )


class BookmarkToggleView(APIView):
    permission_classes = [IsAuthenticated]

    # QA-05: Explicit allowlist prevents bookmarking internal/admin models
    _VALID_CONTENT_TYPES = frozenset(
        {
            "article",
            "researchpaper",
            "repository",
            "video",
            "tweet",
        }
    )

    def post(self, request, content_type_name, object_id):
        """Toggle bookmark for a content object (add if not exists, remove if exists)."""
        # QA-05: validate content type against allowlist before DB lookup
        if content_type_name not in self._VALID_CONTENT_TYPES:
            return Response(
                {
                    "success": False,
                    "error": {
                        "message": f"Invalid content type '{content_type_name}'. "
                        f"Must be one of: {sorted(self._VALID_CONTENT_TYPES)}",
                    },
                },
                status=400,
            )
        try:
            ct = ContentType.objects.get(model=content_type_name)
        except ContentType.DoesNotExist:
            return Response(
                {"success": False, "error": {"message": "Invalid content type"}},
                status=400,
            )

        bookmark, created = UserBookmark.objects.get_or_create(
            user=request.user,
            content_type=ct,
            object_id=str(object_id),
            defaults={
                "notes": request.data.get("notes", ""),
                "tags": request.data.get("tags", []),
            },
        )
        if not created:
            # Log unbookmark activity
            try:
                UserActivity.objects.create(
                    user=request.user,
                    content_type=ct,
                    object_id=str(object_id),
                    interaction_type="unbookmark",
                )
            except Exception:
                pass
            bookmark.delete()
            return Response(
                {
                    "success": True,
                    "data": {"bookmarked": False, "message": "Bookmark removed"},
                }
            )
        # Log bookmark activity
        try:
            UserActivity.objects.create(
                user=request.user,
                content_type=ct,
                object_id=str(object_id),
                interaction_type="bookmark",
            )
        except Exception:
            pass
        serializer = BookmarkSerializer(bookmark)
        return Response(
            {
                "success": True,
                "data": {"bookmarked": True, "bookmark": serializer.data},
            },
            status=201,
        )


class ScraperRunView(APIView):
    """
    POST /scraper/run/
    Trigger a named scraper with optional custom parameters.
    Body: { "scraper": "youtube"|"github"|"hackernews"|"arxiv", "params": {...} }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.core.tasks import (
            scrape_arxiv,
            scrape_github,
            scrape_hackernews,
            scrape_twitter,
            scrape_youtube,
        )

        scraper_id = request.data.get("scraper", "").lower()
        params = request.data.get("params", {}) or {}

        uid = str(request.user.id) if request.user.is_authenticated else None
        SCRAPERS = {
            "youtube": lambda p: scrape_youtube.delay(
                queries=[
                    q.strip() for q in p.get("queries", "").splitlines() if q.strip()
                ]
                or None,
                days_back=int(p.get("days_back", 30)),
                max_results=int(p.get("max_results", 20)),
                user_id=uid,
            ),
            "github": lambda p: scrape_github.delay(
                days_back=1,
                language=p.get("language") if p.get("language") != "All" else None,
                limit=int(p.get("max_repos", 25)),
                user_id=uid,
            ),
            "hackernews": lambda p: scrape_hackernews.delay(
                story_type=p.get("story_type", "top"),
                limit=int(p.get("max_stories", 30)),
                user_id=uid,
            ),
            "arxiv": lambda p: scrape_arxiv.delay(
                categories=[
                    c.strip() for c in p.get("categories", "").splitlines() if c.strip()
                ]
                or None,
                days_back=int(p.get("days_back", 7)),
                max_papers=int(p.get("max_papers", 20)),
                user_id=uid,
            ),
            "twitter": lambda p: scrape_twitter.delay(
                query=p.get("query") or None,
                max_results=int(p.get("max_results", 100)),
                user_id=uid,
            ),
        }

        if scraper_id not in SCRAPERS:
            return Response(
                {
                    "error": f"Unknown scraper: {scraper_id}. Valid: {list(SCRAPERS.keys())}"
                },
                status=400,
            )

        try:
            task = SCRAPERS[scraper_id](params)
            return Response(
                {
                    "success": True,
                    "task_id": task.id,
                    "message": f"{scraper_id.title()} scraper queued (task {task.id[:8]}…)",
                }
            )
        except Exception as exc:
            return Response({"error": str(exc)}, status=500)


class BookmarkNotesView(APIView):
    """PATCH /bookmarks/<id>/notes/ — update the notes on a bookmark."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            bookmark = UserBookmark.objects.get(pk=pk, user=request.user)
        except UserBookmark.DoesNotExist:
            return Response(
                {"success": False, "error": "Bookmark not found"}, status=404
            )
        notes = request.data.get("notes", "")
        bookmark.notes = notes
        bookmark.save(update_fields=["notes"])
        return Response({"success": True, "data": {"notes": bookmark.notes}})


class CollectionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        collections = Collection.objects.filter(user=request.user)
        serializer = CollectionListSerializer(collections, many=True)
        return Response(
            {
                "success": True,
                "data": serializer.data,
                "meta": {"total": collections.count()},
            }
        )

    def post(self, request):
        serializer = CollectionListSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({"success": True, "data": serializer.data}, status=201)
        return Response({"success": False, "error": serializer.errors}, status=400)


class CollectionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return Collection.objects.get(pk=pk, user=user)
        except Collection.DoesNotExist:
            return None

    def get(self, request, pk):
        collection = self.get_object(pk, request.user)
        if not collection:
            return Response(
                {"success": False, "error": {"message": "Not found"}}, status=404
            )
        serializer = CollectionSerializer(collection)
        return Response({"success": True, "data": serializer.data})

    def patch(self, request, pk):
        collection = self.get_object(pk, request.user)
        if not collection:
            return Response(
                {"success": False, "error": {"message": "Not found"}}, status=404
            )
        serializer = CollectionListSerializer(
            collection, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response({"success": True, "data": serializer.data})
        return Response({"success": False, "error": serializer.errors}, status=400)

    def delete(self, request, pk):
        collection = self.get_object(pk, request.user)
        if not collection:
            return Response(
                {"success": False, "error": {"message": "Not found"}}, status=404
            )
        collection.delete()
        return Response(
            {"success": True, "data": {"message": "Collection deleted"}}, status=204
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recommendations(request):
    """
    GET /api/v1/recommendations/

    Content-based recommendations derived from user's recent interactions using
    a single User Interest Vector (mean of recent embeddings).

    Query params:
      - limit (int, default 12, max 50)
      - offset (int, default 0)
    """
    try:
        limit = min(int(request.GET.get("limit", 12)), 50)
    except Exception:
        limit = 12
    try:
        offset = max(int(request.GET.get("offset", 0)), 0)
    except Exception:
        offset = 0

    from django.core.cache import cache  # noqa: PLC0415

    cache_key = f"recs_user_{request.user.id}_l{limit}_o{offset}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    recs = recommend_for_user(request.user, limit=limit, offset=offset)
    data = {
        "articles": ArticleListSerializer(recs["articles"], many=True).data,
        "papers": ResearchPaperSerializer(recs["papers"], many=True).data,
        "repos": RepositorySerializer(recs["repos"], many=True).data,
    }
    total = sum(len(v) for v in data.values())
    response_data = {
        "success": True,
        "data": data,
        "meta": {"total": total, "limit": limit, "offset": offset},
    }
    cache.set(cache_key, response_data, timeout=300)  # Cache recommendations for 5 min
    return Response(response_data)


@api_view(["GET"])
@permission_classes([AllowAny])
def trending(request):
    """
    GET /api/v1/trending/

    Returns trending items across articles, papers, and repositories in the last N hours (default 48),
    scored by weighted user interactions (bookmark > like > view).

    Query params:
      - limit (int, default 20, max 50)
      - hours (int, default 48)
    """
    try:
        limit = min(int(request.GET.get("limit", 20)), 50)
    except Exception:
        limit = 20
    try:
        hours = max(int(request.GET.get("hours", 48)), 1)
    except Exception:
        hours = 48

    from django.core.cache import cache  # noqa: PLC0415

    cache_key = f"trending_l{limit}_h{hours}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    res = get_trending(limit_per_type=limit, hours=hours)

    art_objs = [o for (o, s) in res["articles"]]
    pap_objs = [o for (o, s) in res["papers"]]
    rep_objs = [o for (o, s) in res["repos"]]

    arts = ArticleListSerializer(art_objs, many=True).data
    paps = ResearchPaperSerializer(pap_objs, many=True).data
    reps = RepositorySerializer(rep_objs, many=True).data

    # Inject trend_score preserving the ranking order
    for i, (_, score) in enumerate(res["articles"]):
        if i < len(arts):
            arts[i]["trend_score"] = round(float(score), 3)
    for i, (_, score) in enumerate(res["papers"]):
        if i < len(paps):
            paps[i]["trend_score"] = round(float(score), 3)
    for i, (_, score) in enumerate(res["repos"]):
        if i < len(reps):
            reps[i]["trend_score"] = round(float(score), 3)

    trending_response = {
        "success": True,
        "data": {
            "articles": arts,
            "papers": paps,
            "repos": reps,
        },
        "meta": {
            "limit": limit,
            "hours": hours,
            "since": res["since"].isoformat(),
            "total": len(arts) + len(paps) + len(reps),
        },
    }
    cache.set(cache_key, trending_response, timeout=600)  # Cache trending for 10 min
    return Response(trending_response)


class CollectionBookmarkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Add a bookmark to a collection."""
        try:
            collection = Collection.objects.get(pk=pk, user=request.user)
        except Collection.DoesNotExist:
            return Response(
                {"success": False, "error": {"message": "Not found"}}, status=404
            )
        bookmark_id = request.data.get("bookmark_id")
        try:
            bookmark = UserBookmark.objects.get(pk=bookmark_id, user=request.user)
        except UserBookmark.DoesNotExist:
            return Response(
                {"success": False, "error": {"message": "Bookmark not found"}},
                status=404,
            )
        collection.bookmarks.add(bookmark)
        return Response(
            {"success": True, "data": {"message": "Bookmark added to collection"}}
        )

    def delete(self, request, pk):
        """Remove a bookmark from a collection."""
        try:
            collection = Collection.objects.get(pk=pk, user=request.user)
        except Collection.DoesNotExist:
            return Response(
                {"success": False, "error": {"message": "Not found"}}, status=404
            )
        bookmark_id = request.data.get("bookmark_id")
        try:
            bookmark = UserBookmark.objects.get(pk=bookmark_id, user=request.user)
        except UserBookmark.DoesNotExist:
            return Response(
                {"success": False, "error": {"message": "Bookmark not found"}},
                status=404,
            )
        collection.bookmarks.remove(bookmark)
        return Response(
            {"success": True, "data": {"message": "Bookmark removed from collection"}}
        )


# ── TASK-305-B3: Daily Briefing endpoints ────────────────────────────────────


class TodayBriefingView(APIView):
    """GET /api/briefing/today/ — return today's briefing or 404."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        try:
            briefing = DailyBriefing.objects.get(user=request.user, date=today)
        except DailyBriefing.DoesNotExist:
            # Auto-generate on demand via Celery (non-blocking)
            try:
                from apps.core.tasks import generate_user_briefing

                generate_user_briefing.apply_async(
                    kwargs={"user_id": str(request.user.id)},
                    queue="default",
                )
            except Exception as exc:
                logger.warning("On-demand briefing dispatch failed: %s", exc)

            return Response(
                {
                    "success": False,
                    "error": {
                        "message": "Briefing is being generated. Please refresh in a moment."
                    },
                },
                status=status.HTTP_202_ACCEPTED,
            )
        return Response(
            {
                "success": True,
                "data": {
                    "id": str(briefing.id),
                    "date": briefing.date.isoformat(),
                    "content": briefing.content,
                    "sources": briefing.sources,
                    "topic_summary": briefing.topic_summary,
                    "generated_at": briefing.generated_at.isoformat(),
                },
            }
        )


class ResearchReportPDFView(APIView):
    """
    TASK-601-B4: GET /api/briefing/research/{id}/export-pdf/
    Export a ResearchSession report as a downloadable PDF.
    Uses reportlab for PDF generation.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            from apps.agents.models import ResearchSession  # noqa: PLC0415

            session = ResearchSession.objects.get(pk=pk, user=request.user)
        except Exception:
            return Response({"success": False, "error": "Not found"}, status=404)

        if not session.report:
            return Response(
                {"success": False, "error": "Report not yet generated"}, status=400
            )

        try:
            from io import BytesIO  # noqa: PLC0415

            import reportlab.lib.pagesizes as pagesizes  # noqa: PLC0415
            from reportlab.lib import colors  # noqa: PLC0415
            from reportlab.lib.styles import (  # noqa: PLC0415
                ParagraphStyle,
                getSampleStyleSheet,
            )
            from reportlab.lib.units import inch  # noqa: PLC0415
            from reportlab.platypus import (  # noqa: PLC0415
                Paragraph,
                SimpleDocTemplate,
                Spacer,
            )

            from django.http import HttpResponse  # noqa: PLC0415

            buf = BytesIO()
            doc = SimpleDocTemplate(
                buf,
                pagesize=pagesizes.A4,
                leftMargin=inch,
                rightMargin=inch,
                topMargin=inch,
                bottomMargin=inch,
            )
            styles = getSampleStyleSheet()
            story = []

            # Title
            title_style = ParagraphStyle(
                "Title",
                parent=styles["Title"],
                fontSize=20,
                spaceAfter=20,
                textColor=colors.HexColor("#1e293b"),
            )
            story.append(Paragraph(f"Research Report", title_style))
            story.append(Paragraph(session.query[:200], styles["Heading2"]))
            story.append(Spacer(1, 0.2 * inch))

            # Metadata
            date_str = (
                session.completed_at.strftime("%B %d, %Y")
                if session.completed_at
                else "In progress"
            )
            story.append(
                Paragraph(
                    f"<i>Generated: {date_str} · Synapse AI</i>", styles["Normal"]
                )
            )
            story.append(Spacer(1, 0.3 * inch))

            # Body — strip markdown headers and convert to paragraphs
            import re  # noqa

            for line in session.report.split("\n"):
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 0.1 * inch))
                elif line.startswith("# "):
                    story.append(Paragraph(line[2:], styles["Heading1"]))
                elif line.startswith("## "):
                    story.append(Paragraph(line[3:], styles["Heading2"]))
                elif line.startswith("### "):
                    story.append(Paragraph(line[4:], styles["Heading3"]))
                elif line.startswith("---"):
                    story.append(Spacer(1, 0.2 * inch))
                else:
                    # Replace markdown bold/italic
                    line = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", line)
                    line = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", line)
                    story.append(Paragraph(line, styles["Normal"]))

            doc.build(story)

            buf.seek(0)
            filename = f"research-report-{str(session.id)[:8]}.pdf"
            response = HttpResponse(buf, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        except ImportError:
            # reportlab not installed — return markdown as plain text download
            from django.http import HttpResponse  # noqa: PLC0415

            response = HttpResponse(session.report, content_type="text/markdown")
            response["Content-Disposition"] = (
                f'attachment; filename="research-report-{str(session.id)[:8]}.md"'
            )
            return response
        except Exception as exc:
            logger.error("PDF export failed for session %s: %s", pk, exc)
            return Response(
                {"success": False, "error": "PDF generation failed"}, status=500
            )


class BriefingHistoryView(APIView):
    """GET /api/briefing/history/ — last 7 days of briefings."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        briefings = DailyBriefing.objects.filter(user=request.user).order_by("-date")[
            :7
        ]
        data = [
            {
                "id": str(b.id),
                "date": b.date.isoformat(),
                "content": b.content,
                "sources": b.sources,
                "topic_summary": b.topic_summary,
                "generated_at": b.generated_at.isoformat(),
            }
            for b in briefings
        ]
        return Response({"success": True, "data": data})


# ── TASK-603-B3: Knowledge Graph API ─────────────────────────────────────────


def _serialize_node(node: KnowledgeNode) -> dict:
    return {
        "id": str(node.id),
        "name": node.name,
        "entity_type": node.entity_type,
        "description": node.description,
        "mention_count": node.mention_count,
        "metadata": node.metadata,
    }


def _serialize_edge(edge: KnowledgeEdge) -> dict:
    try:
        src_name = edge.source.name
    except Exception:
        src_name = ""
    try:
        tgt_name = edge.target.name
    except Exception:
        tgt_name = ""
    return {
        "id": str(edge.id),
        "source": str(edge.source_id),
        "target": str(edge.target_id),
        "source_name": src_name,
        "target_name": tgt_name,
        "relation_type": edge.relation_type,
        "weight": edge.weight,
    }


class KnowledgeGraphView(APIView):
    """
    GET /api/knowledge-graph/?center={node_id}&depth=2
    Return a subgraph (nodes + edges) centred on a node up to `depth` hops.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        center_id = request.query_params.get("center")
        depth = min(int(request.query_params.get("depth", 2)), 3)
        limit = min(int(request.query_params.get("limit", 50)), 200)
        entity_type = request.query_params.get("type", "")

        if center_id:
            try:
                center = KnowledgeNode.objects.get(pk=center_id)
            except KnowledgeNode.DoesNotExist:
                return Response(
                    {"success": False, "error": "Node not found"}, status=404
                )

            # BFS expansion up to `depth` hops
            visited_ids = {str(center.id)}
            frontier = [center]
            all_nodes = [center]
            all_edges = []

            for _ in range(depth):
                if not frontier:
                    break
                ids = [n.id for n in frontier]
                edges = list(
                    KnowledgeEdge.objects.filter(
                        Q(source_id__in=ids) | Q(target_id__in=ids)
                    ).select_related("source", "target")[:limit]
                )
                all_edges.extend(edges)
                new_frontier = []
                for edge in edges:
                    for node in (edge.source, edge.target):
                        nid = str(node.id)
                        if nid not in visited_ids:
                            visited_ids.add(nid)
                            all_nodes.append(node)
                            new_frontier.append(node)
                frontier = new_frontier

        else:
            # No center: return top nodes by mention count
            qs = KnowledgeNode.objects.all().order_by("-mention_count")
            if entity_type:
                qs = qs.filter(entity_type=entity_type)
            all_nodes = list(qs[:limit])
            ids = [n.id for n in all_nodes]
            all_edges = list(
                KnowledgeEdge.objects.filter(
                    source_id__in=ids, target_id__in=ids
                ).select_related("source", "target").order_by("-weight")[: limit * 2]
            )

        return Response(
            {
                "success": True,
                "data": {
                    "nodes": [_serialize_node(n) for n in all_nodes],
                    "edges": [_serialize_edge(e) for e in all_edges],
                },
            }
        )


class KnowledgeGraphSearchView(APIView):
    """GET /api/knowledge-graph/search/?q={query} — find nodes by name."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        entity_type = request.query_params.get("type", "")
        limit = min(int(request.query_params.get("limit", 20)), 100)

        if not q:
            return Response({"success": False, "error": "q is required"}, status=400)

        qs = KnowledgeNode.objects.filter(name__icontains=q).order_by("-mention_count")
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        nodes = qs[:limit]

        return Response(
            {
                "success": True,
                "data": [_serialize_node(n) for n in nodes],
            }
        )


class AuditLogListView(APIView):
    """
    TASK-505-B3: GET /api/audit-log/ — list audit log entries (paginated).
    Admins see all users; regular users see only their own.

    Query params:
        ?action=login|api_key_created|...   filter by action type
        ?limit=50                            items per page (default 50, max 200)
        ?offset=0                            pagination offset
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            AuditLog.objects.all().select_related("user")
            if request.user.is_staff
            else AuditLog.objects.filter(user=request.user)
        )
        action_filter = request.query_params.get("action", "")
        if action_filter:
            qs = qs.filter(action=action_filter)

        # Pagination — default 50, max 200
        limit = min(int(request.query_params.get("limit", 50)), 200)
        offset = int(request.query_params.get("offset", 0))
        total = qs.count()
        qs = qs.order_by("-created_at")[offset : offset + limit]

        data = [
            {
                "id": str(entry.id),
                "action": entry.action,
                "user": entry.user.email if entry.user else "anonymous",
                "target_id": entry.target_id,
                "target_type": entry.target_type,
                "ip_address": entry.ip_address,
                "metadata": entry.metadata,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in qs
        ]
        return Response(
            {
                "success": True,
                "count": total,
                "next": offset + limit < total,
                "data": data,
            }
        )


class KnowledgeNodeDetailView(APIView):
    """GET /api/knowledge-graph/nodes/{id}/ — node detail with connected nodes."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            node = KnowledgeNode.objects.get(pk=pk)
        except KnowledgeNode.DoesNotExist:
            return Response({"success": False, "error": "Not found"}, status=404)

        outgoing = list(
            KnowledgeEdge.objects.filter(source=node).select_related("target")[:20]
        )
        incoming = list(
            KnowledgeEdge.objects.filter(target=node).select_related("source")[:20]
        )

        return Response(
            {
                "success": True,
                "data": {
                    **_serialize_node(node),
                    "source_ids": node.source_ids[:10],
                    "outgoing_edges": [
                        {
                            **_serialize_edge(e),
                            "target_name": e.target.name,
                            "target_type": e.target.entity_type,
                        }
                        for e in outgoing
                    ],
                    "incoming_edges": [
                        {
                            **_serialize_edge(e),
                            "source_name": e.source.name,
                            "source_type": e.source.entity_type,
                        }
                        for e in incoming
                    ],
                },
            }
        )


class APIStatusView(APIView):
    """GET /api/api-status/ — return API configuration status for user warnings."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .api_status import get_api_status

        status = get_api_status()
        return Response({"success": True, "data": status})
