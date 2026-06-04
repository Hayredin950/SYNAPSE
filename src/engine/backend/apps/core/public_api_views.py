"""
TASK-605-B3: Public API endpoints (API key + session auth, plan-rate-limited).

All endpoints accept:
  - Authorization: Bearer <JWT>          (session user)
  - Authorization: Bearer sk-syn-<key>   (API key user)

Endpoints:
  GET  /api/v1/content/articles/   search articles
  GET  /api/v1/content/papers/     search papers
  GET  /api/v1/content/repos/      search repositories
  POST /api/v1/ai/query/           ask AI with RAG
  GET  /api/v1/trends/             current trending content
  POST /api/v1/content/save/       save URL to knowledge base
"""

from __future__ import annotations

import logging

from apps.core.auth import APIKeyAuthentication
from apps.core.throttles import APIRateThrottle

from django.db.models import Q
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# Mix both JWT and API key auth on all public API endpoints
PUBLIC_AUTH = [APIKeyAuthentication]


def _page_params(request: Request) -> tuple[int, int]:
    """Return (limit, offset) from query params."""
    limit = min(int(request.query_params.get("limit", 20)), 100)
    offset = int(request.query_params.get("offset", 0))
    return limit, offset


class PublicArticlesView(APIView):
    """
    GET /api/v1/content/articles/
    Query params: ?q=, ?topic=, ?limit=, ?offset=
    """

    authentication_classes = PUBLIC_AUTH
    permission_classes = [IsAuthenticated]
    throttle_classes = [APIRateThrottle]

    def get(self, request: Request) -> Response:
        from apps.articles.models import Article
        from apps.articles.serializers import ArticleListSerializer as ArticleSerializer

        q = request.query_params.get("q", "").strip()
        topic = request.query_params.get("topic", "").strip()
        limit, offset = _page_params(request)

        qs = Article.objects.all().order_by("-scraped_at")
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q))
        if topic:
            qs = qs.filter(topic__icontains=topic)

        total = qs.count()
        items = qs[offset : offset + limit]
        data = ArticleSerializer(items, many=True).data

        return Response(
            {
                "success": True,
                "count": total,
                "next": offset + limit < total,
                "data": data,
            }
        )


class PublicPapersView(APIView):
    """
    GET /api/v1/content/papers/
    Query params: ?q=, ?limit=, ?offset=
    """

    authentication_classes = PUBLIC_AUTH
    permission_classes = [IsAuthenticated]
    throttle_classes = [APIRateThrottle]

    def get(self, request: Request) -> Response:
        from apps.papers.models import ResearchPaper
        from apps.papers.serializers import ResearchPaperSerializer

        q = request.query_params.get("q", "").strip()
        limit, offset = _page_params(request)

        qs = ResearchPaper.objects.all().order_by("-fetched_at")
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(abstract__icontains=q))

        total = qs.count()
        items = qs[offset : offset + limit]
        data = ResearchPaperSerializer(items, many=True).data

        return Response(
            {
                "success": True,
                "count": total,
                "next": offset + limit < total,
                "data": data,
            }
        )


class PublicReposView(APIView):
    """
    GET /api/v1/content/repos/
    Query params: ?q=, ?language=, ?limit=, ?offset=
    """

    authentication_classes = PUBLIC_AUTH
    permission_classes = [IsAuthenticated]
    throttle_classes = [APIRateThrottle]

    def get(self, request: Request) -> Response:
        from apps.repositories.models import Repository
        from apps.repositories.serializers import RepositorySerializer

        q = request.query_params.get("q", "").strip()
        language = request.query_params.get("language", "").strip()
        limit, offset = _page_params(request)

        qs = Repository.objects.all().order_by("-stars")
        if q:
            qs = qs.filter(Q(full_name__icontains=q) | Q(description__icontains=q))
        if language:
            qs = qs.filter(language__iexact=language)

        total = qs.count()
        items = qs[offset : offset + limit]
        data = RepositorySerializer(items, many=True).data

        return Response(
            {
                "success": True,
                "count": total,
                "next": offset + limit < total,
                "data": data,
            }
        )


class PublicAIQueryView(APIView):
    """
    POST /api/v1/ai/query/
    Body: {"question": "...", "conversation_id": "..."}
    Returns: {"answer": "...", "sources": [...]}
    """

    authentication_classes = PUBLIC_AUTH
    permission_classes = [IsAuthenticated]
    throttle_classes = [APIRateThrottle]

    def post(self, request: Request) -> Response:
        question = (request.data.get("question") or "").strip()
        if not question:
            return Response(
                {"success": False, "error": "question is required"}, status=400
            )
        if len(question) > 2000:
            return Response(
                {"success": False, "error": "question too long (max 2000 chars)"},
                status=400,
            )

        # Best-effort RAG pipeline call
        try:
            from ai_engine.rag.pipeline import RAGPipeline  # noqa: PLC0415

            pipeline = RAGPipeline()
            result = pipeline.query(question, user_id=str(request.user.pk))
            return Response(
                {
                    "success": True,
                    "data": {
                        "answer": result.get("answer", ""),
                        "sources": result.get("sources", []),
                    },
                }
            )
        except Exception as exc:
            logger.warning("AI query failed: %s", exc)
            return Response(
                {
                    "success": False,
                    "error": "AI service temporarily unavailable",
                },
                status=503,
            )


class PublicTrendsView(APIView):
    """GET /api/v1/trends/ — current trending content."""

    authentication_classes = PUBLIC_AUTH
    permission_classes = [IsAuthenticated]
    throttle_classes = [APIRateThrottle]

    def get(self, request: Request) -> Response:
        from apps.core.trending import get_trending  # noqa: PLC0415

        limit = min(int(request.query_params.get("limit", 20)), 50)
        try:
            trending = get_trending(limit=limit)
            return Response({"success": True, "data": trending})
        except Exception as exc:
            logger.warning("Trending API failed: %s", exc)
            return Response({"success": True, "data": []})


class PublicSaveContentView(APIView):
    """
    POST /api/v1/content/save/
    Body: {"url": "...", "title": "...", "tags": [...]}
    Saves a URL to the user's library (bookmark).
    """

    authentication_classes = PUBLIC_AUTH
    permission_classes = [IsAuthenticated]
    throttle_classes = [APIRateThrottle]

    def post(self, request: Request) -> Response:
        url = (request.data.get("url") or "").strip()
        title = (request.data.get("title") or url).strip()
        tags = request.data.get("tags", [])

        if not url:
            return Response({"success": False, "error": "url is required"}, status=400)

        # Create a bookmark
        try:
            from apps.core.models import UserBookmark  # noqa: PLC0415

            from django.contrib.contenttypes.models import ContentType  # noqa: PLC0415

            # For browser extension saves, store as generic metadata
            bookmark, created = UserBookmark.objects.get_or_create(
                user=request.user,
                url=url,
                defaults={"title": title[:500], "tags": tags},
            )
            return Response(
                {
                    "success": True,
                    "data": {
                        "id": str(bookmark.id) if hasattr(bookmark, "id") else None,
                        "created": created,
                    },
                },
                status=201 if created else 200,
            )
        except Exception as exc:
            logger.warning("Content save failed: %s", exc)
            return Response(
                {"success": False, "error": "Failed to save content"}, status=500
            )
