from apps.core.pagination import StandardPagination
from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Tweet
from .serializers import TweetDetailSerializer, TweetListSerializer


class TweetListView(ListAPIView):
    serializer_class = TweetListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["topic", "author_username", "lang", "is_retweet"]
    search_fields = ["text", "author_username", "author_display_name"]
    ordering_fields = [
        "posted_at",
        "trending_score",
        "like_count",
        "retweet_count",
        "view_count",
        "scraped_at",
    ]
    ordering = ["-posted_at"]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Tweet.objects.all()
        # ── Personalization: scope to tweets linked via UserTweet junction ──
        if self.request.user and self.request.user.is_authenticated:
            qs = qs.filter(user_tweets__user=self.request.user)
        tag = self.request.GET.get("tag")
        if tag:
            qs = qs.filter(hashtags__icontains=tag)
        topic = self.request.GET.get("topic")
        if topic and topic != "All":
            qs = qs.filter(topic__iexact=topic)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(text__icontains=q)
                | Q(author_username__icontains=q)
                | Q(author_display_name__icontains=q)
            )
        return qs


class TweetDetailView(RetrieveAPIView):
    serializer_class = TweetDetailSerializer
    permission_classes = [AllowAny]
    queryset = Tweet.objects.all()


class TrendingTweetListView(ListAPIView):
    serializer_class = TweetListSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPagination

    def get_queryset(self):
        return Tweet.objects.order_by("-trending_score", "-like_count", "-posted_at")


@api_view(["GET"])
@permission_classes([AllowAny])
def tweet_topics(request):
    from django.core.cache import cache

    cache_key = "tweet_topics_list"
    topics = cache.get(cache_key)
    if topics is None:
        topics = list(
            Tweet.objects.exclude(topic="")
            .values_list("topic", flat=True)
            .distinct()
            .order_by("topic")
        )
        cache.set(cache_key, topics, timeout=3600)
    return Response({"success": True, "data": topics})


@api_view(["GET"])
@permission_classes([AllowAny])
def tweet_search(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return Response(
            {"success": False, "error": {"message": "Query parameter q is required"}},
            status=400,
        )
    results = Tweet.objects.filter(
        Q(text__icontains=q)
        | Q(author_username__icontains=q)
        | Q(author_display_name__icontains=q)
    ).order_by("-trending_score")[:20]
    serializer = TweetListSerializer(results, many=True)
    return Response(
        {
            "success": True,
            "data": serializer.data,
            "meta": {"query": q, "total": len(serializer.data)},
        }
    )
