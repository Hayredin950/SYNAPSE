import logging

from apps.core.models import UserActivity
from apps.core.pagination import StandardPagination
from django_filters.rest_framework import DjangoFilterBackend

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from .models import Article
from .serializers import ArticleDetailSerializer, ArticleListSerializer

logger = logging.getLogger(__name__)


class ArticleListView(ListAPIView):
    serializer_class = ArticleListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["topic", "source__source_type"]
    search_fields = ["title", "summary", "author", "topic"]
    ordering_fields = ["published_at", "trending_score", "view_count", "scraped_at"]
    ordering = ["-published_at"]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Article.objects.select_related("source").all()
        # ── Saved feed: only show bookmarked articles when ?saved=1 ──
        saved = self.request.GET.get("saved") == "1"
        if saved and self.request.user and self.request.user.is_authenticated:
            qs = qs.filter(user_articles__user=self.request.user)
        # Tag filtering
        tag = self.request.GET.get("tag")
        if tag:
            qs = qs.filter(tags__icontains=tag)
        # Topic filtering
        topic = self.request.GET.get("topic")
        if topic and topic != "All":
            qs = qs.filter(topic__iexact=topic)
        # Full-text search
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(summary__icontains=q)
                | Q(author__icontains=q)
                | Q(topic__icontains=q)
            )
        # Interest-based filtering: applied when ?for_you=1 and user has onboarding prefs
        for_you = self.request.GET.get("for_you") == "1"
        if for_you and self.request.user and self.request.user.is_authenticated:
            try:
                from apps.users.models import OnboardingPreferences

                prefs = OnboardingPreferences.objects.get(
                    user=self.request.user, completed=True
                )
                interests = prefs.interests  # list of topic strings e.g. ["AI", "Python"]
                if interests:
                    # Match by title, summary, topic, or tags — since HN articles
                    # all have generic topic="tech", title-matching is most effective.
                    interest_q = Q()
                    for interest in interests:
                        interest_q |= Q(title__icontains=interest)
                        interest_q |= Q(summary__icontains=interest)
                        interest_q |= Q(topic__icontains=interest)
                        interest_q |= Q(tags__icontains=interest.lower())
                    personalized = qs.filter(interest_q)
                    # Only apply filter if it returns results — otherwise fall back to all
                    if personalized.exists():
                        qs = personalized
                    logger.info(
                        "interest_feed_filtered: user=%s interests=%s count=%s",
                        self.request.user.email,
                        interests,
                        qs.count(),
                    )
            except Exception:
                # Any error (no prefs, not completed, etc.) → return unfiltered feed
                pass
        return qs


class ArticleDetailView(RetrieveAPIView):
    serializer_class = ArticleDetailSerializer
    permission_classes = [AllowAny]
    queryset = Article.objects.select_related("source").all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.view_count += 1
        instance.save(update_fields=["view_count"])
        # Log view activity (Phase 2.4)
        try:
            ct = ContentType.objects.get_for_model(Article)
            if request.user and request.user.is_authenticated:
                UserActivity.objects.create(
                    user=request.user,
                    content_type=ct,
                    object_id=str(instance.id),
                    interaction_type="view",
                )
        except Exception:
            pass
        serializer = self.get_serializer(instance)
        return Response({"success": True, "data": serializer.data})


class TrendingArticleListView(ListAPIView):
    serializer_class = ArticleListSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPagination

    def get_queryset(self):
        # Do NOT slice here — sliced querysets cannot be paginated (count() breaks).
        # The pagination class will apply its own limit, and the meta.total will
        # reflect the real DB count so the home-page stat cards display correctly.
        return Article.objects.select_related("source").order_by(
            "-trending_score", "-published_at"
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def article_topics(request):
    from django.core.cache import cache  # noqa: PLC0415

    cache_key = "article_topics_list"
    topics = cache.get(cache_key)
    if topics is None:
        topics = list(
            Article.objects.exclude(topic="")
            .values_list("topic", flat=True)
            .distinct()
            .order_by("topic")
        )
        cache.set(cache_key, topics, timeout=3600)  # Cache for 1 hour — stable data
    return Response({"success": True, "data": topics})


@api_view(["GET"])
@permission_classes([AllowAny])
def article_search(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return Response(
            {"success": False, "error": {"message": "Query parameter q is required"}},
            status=400,
        )
    results = (
        Article.objects.filter(
            Q(title__icontains=q)
            | Q(summary__icontains=q)
            | Q(author__icontains=q)
            | Q(topic__icontains=q)
        )
        .select_related("source")
        .order_by("-trending_score")[:20]
    )
    serializer = ArticleListSerializer(results, many=True)
    return Response(
        {
            "success": True,
            "data": serializer.data,
            "meta": {"query": q, "total": len(serializer.data)},
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def trigger_summarization(request):
    """
    Manually trigger summarization of pending articles.

    POST /api/v1/articles/summarize/
    Optional body: { "batch_size": 20 }

    This endpoint is called by the frontend when the feed loads so that
    summaries are generated even if the Celery beat worker is not running.
    It is intentionally open (AllowAny) for development; restrict to
    IsAdminUser or IsAuthenticated in production if preferred.
    """
    from .tasks import summarize_pending_articles  # noqa: PLC0415

    batch_size = int(request.data.get("batch_size", 20))
    batch_size = max(1, min(batch_size, 50))  # clamp 1–50

    # By default, also clear the "permanently failed" sentinel from articles so
    # they retry once the LLM provider is healthy again. The frontend can
    # disable this by passing reset_failed=false. This makes the system
    # self-heal whenever a user opens the feed AFTER an LLM key is
    # (re)configured — no shell access required.
    reset_failed = request.data.get("reset_failed", True)

    # Count how many articles actually need summaries before dispatching
    from django.db.models import Q as DQ  # noqa: PLC0415

    from .tasks import SUMMARY_FAILED_SENTINEL  # noqa: PLC0415

    sentinel_cleared = 0
    if reset_failed:
        sentinel_cleared = Article.objects.filter(
            summary=SUMMARY_FAILED_SENTINEL
        ).update(summary="")
        if sentinel_cleared:
            logger.info(
                "trigger_summarization: auto-cleared %d failure sentinel(s) "
                "(self-heal after LLM provider recovered)",
                sentinel_cleared,
            )

    pending_count = (
        Article.objects.filter(DQ(summary="") | DQ(summary__isnull=True))
        .exclude(summary=SUMMARY_FAILED_SENTINEL)
        .count()
    )

    if pending_count == 0:
        return Response(
            {
                "success": True,
                "message": "No articles pending summarization.",
                "pending": 0,
                "queued": 0,
                "sentinel_cleared": sentinel_cleared,
            }
        )

    try:
        task = summarize_pending_articles.delay(batch_size)
        logger.info(
            "trigger_summarization: dispatched summarize_pending_articles "
            "(task_id=%s, pending=%d, batch_size=%d, sentinel_cleared=%d)",
            task.id,
            pending_count,
            batch_size,
            sentinel_cleared,
        )
        return Response(
            {
                "success": True,
                "message": (
                    f"Summarization task queued for up to {batch_size} articles."
                    + (
                        f" Cleared {sentinel_cleared} stuck article(s) for retry."
                        if sentinel_cleared
                        else ""
                    )
                ),
                "task_id": task.id,
                "pending": pending_count,
                "queued": min(pending_count, batch_size),
                "sentinel_cleared": sentinel_cleared,
            }
        )
    except Exception as exc:
        logger.error(
            "trigger_summarization: failed to dispatch task: %s", exc, exc_info=True
        )
        return Response(
            {"success": False, "error": str(exc)},
            status=500,
        )
