from apps.core.pagination import StandardPagination
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters, generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Video
from .serializers import VideoDetailSerializer, VideoSerializer


class VideoListView(generics.ListAPIView):
    serializer_class = VideoSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["title", "description", "channel_name", "topics"]
    ordering_fields = ["published_at", "view_count", "like_count", "fetched_at"]
    ordering = ["-fetched_at"]

    def get_queryset(self):
        qs = Video.objects.all()
        # ── Saved feed: only filter to the user's bookmarked videos when
        # ?saved=1 — global feed by default, matching the articles/repos views.
        # (Filtering unconditionally on auth made logged-in users see 0 videos
        # because the scrapers store content globally, not per-user.)
        saved = self.request.query_params.get("saved", "").lower() in ("true", "1")
        if saved and self.request.user and self.request.user.is_authenticated:
            qs = qs.filter(user_videos__user=self.request.user)
        # ── Personalized feed: ?for_you=1 filters by interest slugs ──
        if self.request.query_params.get("for_you") == "1":
            from apps.users.interests import apply_for_you_filter  # noqa: PLC0415

            qs = apply_for_you_filter(
                qs, self.request, text_fields=("title", "description"), topic_field=None
            )
        return qs


class VideoDetailView(generics.RetrieveAPIView):
    queryset = Video.objects.all()
    serializer_class = VideoDetailSerializer
    permission_classes = [AllowAny]

    def retrieve(self, request, *args, **kwargs):
        return Response(
            {"success": True, "data": self.get_serializer(self.get_object()).data}
        )


class TrendingVideoListView(generics.ListAPIView):
    serializer_class = VideoSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPagination
    queryset = Video.objects.order_by("-view_count")
