import uuid

from pgvector.django import VectorField

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models


class Video(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    youtube_id = models.CharField(max_length=50, unique=True)
    title = models.TextField()
    description = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    channel_name = models.CharField(max_length=300, blank=True)
    channel_id = models.CharField(max_length=300, blank=True)
    url = models.URLField(max_length=1000)
    thumbnail_url = models.URLField(max_length=1000, blank=True)
    duration_seconds = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    transcript = models.TextField(blank=True)
    topics = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    embedding_id = models.CharField(max_length=200, blank=True)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "videos"
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["published_at"]),
            models.Index(fields=["channel_name"]),
        ]

    def __str__(self):
        return self.title[:80]


class UserVideo(models.Model):
    """Junction table linking users to globally-stored videos."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_videos"
    )
    video = models.ForeignKey(
        Video, on_delete=models.CASCADE, related_name="user_videos"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_videos"
        unique_together = ("user", "video")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user} ↔ {self.video}"
