from rest_framework import serializers

from .models import Video


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = [
            "id",
            "youtube_id",
            "title",
            "description",
            "summary",
            "channel_name",
            "url",
            "thumbnail_url",
            "duration_seconds",
            "view_count",
            "like_count",
            "published_at",
            "topics",
            "fetched_at",
        ]


class VideoDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = "__all__"
