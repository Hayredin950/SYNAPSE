import django_filters
from apps.core.pagination import StandardPagination
from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Avg, Count, Sum
from rest_framework import filters, generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Repository
from .serializers import RepositorySerializer


class RepositoryFilter(django_filters.FilterSet):
    language = django_filters.CharFilter(lookup_expr="iexact")
    stars_min = django_filters.NumberFilter(field_name="stars", lookup_expr="gte")
    trending = django_filters.BooleanFilter(field_name="is_trending")

    class Meta:
        model = Repository
        fields = ["language", "stars_min", "trending"]


class RepositoryListView(generics.ListAPIView):
    serializer_class = RepositorySerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = RepositoryFilter
    search_fields = ["name", "description", "owner", "topics"]
    ordering_fields = ["stars", "forks", "stars_today", "scraped_at"]
    ordering = ["-stars"]

    def get_queryset(self):
        from django.db.models import Q

        qs = Repository.objects.all()
        # ── Saved feed: only filter to bookmarked repos when ?saved=1 ──
        saved = self.request.GET.get("saved") == "1"
        if saved and self.request.user and self.request.user.is_authenticated:
            qs = qs.filter(user_repositories__user=self.request.user)
        return qs


class RepositoryDetailView(generics.RetrieveAPIView):
    queryset = Repository.objects.all()
    serializer_class = RepositorySerializer
    permission_classes = [AllowAny]

    def retrieve(self, request, *args, **kwargs):
        return Response(
            {"success": True, "data": self.get_serializer(self.get_object()).data}
        )


class TrendingRepositoryListView(generics.ListAPIView):
    serializer_class = RepositorySerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Repository.objects.filter(is_trending=True).order_by("-stars_today")
        saved = self.request.GET.get("saved") == "1"
        if saved and self.request.user and self.request.user.is_authenticated:
            qs = qs.filter(user_repositories__user=self.request.user)
        return qs


# ── TASK-602-B3: GitHub Intelligence API endpoints ────────────────────────────

from rest_framework.views import APIView  # noqa: E402


class GitHubTrendingView(APIView):
    """
    GET /api/v1/repos/trending-velocity/
    Repos sorted by 7-day star velocity.
    Query params: ?language=python, ?topic=llm, ?limit=20
    """

    permission_classes = [AllowAny]

    def get(self, request):
        language = request.query_params.get("language", "").strip().lower()
        topic = request.query_params.get("topic", "").strip().lower()
        limit = min(int(request.query_params.get("limit", 200)), 500)

        qs = Repository.objects.all().order_by("-velocity_7d", "-stars")
        if request.user and request.user.is_authenticated:
            qs = qs.filter(user_repositories__user=request.user)
        if language:
            qs = qs.filter(language__iexact=language)
        if topic:
            qs = qs.filter(topics__icontains=topic)
        qs = qs[:limit]

        data = [
            {
                "id": str(r.id),
                "full_name": r.full_name,
                "url": r.url,
                "description": r.description,
                "language": r.language,
                "stars": r.stars,
                "forks": r.forks,
                "stars_7d_delta": r.stars_7d_delta,
                "velocity_7d": r.velocity_7d,
                "velocity_30d": r.velocity_30d,
                "trend_class": r.trend_class,
                "is_rising_star": r.is_rising_star,
                "star_history": r.star_history[-14:] if r.star_history else [],
                "topics": r.topics,
            }
            for r in qs
        ]
        return Response({"success": True, "data": data})


class GitHubEcosystemView(APIView):
    """
    GET /api/v1/repos/ecosystem/{language}/
    Language health: total repos, avg star growth, top repos.
    """

    permission_classes = [AllowAny]

    def get(self, request, language: str):
        qs = Repository.objects.filter(language__iexact=language)
        if request.user and request.user.is_authenticated:
            qs = qs.filter(user_repositories__user=request.user)
        total = qs.count()
        if total == 0:
            return Response(
                {"success": False, "error": f"No repos found for {language}"},
                status=404,
            )

        agg = qs.aggregate(
            avg_stars=Avg("stars"),
            avg_velocity_7d=Avg("velocity_7d"),
            avg_velocity_30d=Avg("velocity_30d"),
            total_stars=Sum("stars"),
            rising_count=Count(
                "id", filter=__import__("django").db.models.Q(trend_class="rising_star")
            ),
        )

        top_repos = qs.order_by("-velocity_7d", "-stars")[:10]
        top_data = [
            {
                "full_name": r.full_name,
                "url": r.url,
                "stars": r.stars,
                "velocity_7d": r.velocity_7d,
                "trend_class": r.trend_class,
            }
            for r in top_repos
        ]

        return Response(
            {
                "success": True,
                "data": {
                    "language": language,
                    "total_repos": total,
                    "total_stars": agg["total_stars"] or 0,
                    "avg_stars": round(agg["avg_stars"] or 0, 1),
                    "avg_velocity_7d": round(agg["avg_velocity_7d"] or 0, 2),
                    "avg_velocity_30d": round(agg["avg_velocity_30d"] or 0, 2),
                    "rising_star_count": agg["rising_count"],
                    "top_repos": top_data,
                },
            }
        )


class GitHubRepoAnalysisView(APIView):
    """
    GET /api/v1/repos/{id}/analysis/
    Full repo analysis: growth chart, tech stack, similar repos.
    """

    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            repo = Repository.objects.get(pk=pk)
        except Repository.DoesNotExist:
            return Response({"success": False, "error": "Not found"}, status=404)

        # Similar repos: same language, similar star range (±50%)
        similar = (
            Repository.objects.filter(language__iexact=repo.language or "")
            .exclude(pk=pk)
            .order_by("-velocity_7d")[:5]
        )

        return Response(
            {
                "success": True,
                "data": {
                    "id": str(repo.id),
                    "full_name": repo.full_name,
                    "url": repo.url,
                    "description": repo.description,
                    "language": repo.language,
                    "topics": repo.topics,
                    "stars": repo.stars,
                    "forks": repo.forks,
                    "stars_7d_delta": repo.stars_7d_delta,
                    "stars_30d_delta": repo.stars_30d_delta,
                    "velocity_7d": repo.velocity_7d,
                    "velocity_30d": repo.velocity_30d,
                    "trend_class": repo.trend_class,
                    "is_rising_star": repo.is_rising_star,
                    "star_history": repo.star_history,
                    "contributor_count": repo.contributor_count,
                    "open_issues": repo.open_issues,
                    "last_commit_date": (
                        repo.last_commit_date.isoformat()
                        if repo.last_commit_date
                        else None
                    ),
                    "similar_repos": [
                        {
                            "full_name": r.full_name,
                            "url": r.url,
                            "stars": r.stars,
                            "velocity_7d": r.velocity_7d,
                        }
                        for r in similar
                    ],
                },
            }
        )
