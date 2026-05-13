import uuid

from pgvector.django import VectorField

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models


class Repository(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    github_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=500)
    full_name = models.CharField(max_length=500, unique=True)
    description = models.TextField(blank=True)
    url = models.URLField(max_length=1000)
    clone_url = models.URLField(max_length=1000, blank=True)
    stars = models.IntegerField(default=0)
    forks = models.IntegerField(default=0)
    watchers = models.IntegerField(default=0)
    open_issues = models.IntegerField(default=0)
    language = models.CharField(max_length=100, blank=True)
    topics = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    owner = models.CharField(max_length=200)
    is_trending = models.BooleanField(default=False)
    readme_summary = models.TextField(blank=True)
    embedding_id = models.CharField(max_length=200, blank=True)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now=True)

    # ── TASK-602-B1: Star velocity + trend classification ─────────────────────
    class TrendClass(models.TextChoices):
        RISING_STAR = "rising_star", "Rising Star"
        STABLE = "stable", "Stable"
        DECLINING = "declining", "Declining"

    stars_7d_delta = models.IntegerField(default=0)
    stars_30d_delta = models.IntegerField(default=0)
    velocity_7d = models.FloatField(default=0.0)
    velocity_30d = models.FloatField(default=0.0)
    trend_class = models.CharField(
        max_length=20,
        choices=TrendClass.choices,
        default=TrendClass.STABLE,
        db_index=True,
    )
    star_history = models.JSONField(default=list)
    last_commit_date = models.DateTimeField(null=True, blank=True)
    contributor_count = models.IntegerField(default=0)
    is_rising_star = models.BooleanField(default=False, db_index=True)
    repo_created_at = models.DateTimeField(null=True, blank=True)
    stars_today = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "repositories"
        ordering = ["-stars"]
        indexes = [
            models.Index(fields=["language"]),
            models.Index(fields=["is_trending"]),
            models.Index(fields=["stars"]),
        ]

    def __str__(self):
        return self.full_name


class UserRepository(models.Model):
    """Junction table linking users to globally-stored repositories."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_repositories",
    )
    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name="user_repositories"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_repositories"
        unique_together = ("user", "repository")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user} ↔ {self.repository}"
