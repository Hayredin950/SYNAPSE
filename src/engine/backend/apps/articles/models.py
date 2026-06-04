import uuid

from pgvector.django import VectorField

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models


class Source(models.Model):
    class SourceType(models.TextChoices):
        NEWS = "news", "News"
        GITHUB = "github", "GitHub"
        ARXIV = "arxiv", "arXiv"
        YOUTUBE = "youtube", "YouTube"
        BLOG = "blog", "Blog"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=500, unique=True)
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    is_active = models.BooleanField(default=True)
    scrape_interval_minutes = models.IntegerField(default=30)
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sources"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.source_type})"


class Article(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.TextField()
    content = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    url = models.URLField(max_length=1000, unique=True)
    source = models.ForeignKey(
        Source, on_delete=models.SET_NULL, null=True, related_name="articles"
    )
    author = models.CharField(max_length=300, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)
    topic = models.CharField(max_length=100, blank=True)
    tags = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    keywords = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    sentiment_score = models.FloatField(null=True, blank=True)
    trending_score = models.FloatField(default=0.0)
    view_count = models.IntegerField(default=0)
    embedding_id = models.CharField(max_length=200, blank=True)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    url_hash = models.CharField(max_length=64, unique=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    nlp_processed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True once the NLP pipeline (keywords, topic, sentiment) has run.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "articles"
        ordering = ["-published_at", "-scraped_at"]
        indexes = [
            models.Index(fields=["topic"]),
            models.Index(fields=["trending_score"]),
            models.Index(fields=["published_at"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self):
        return self.title[:80]

    def save(self, *args, **kwargs):
        if not self.url_hash:
            import hashlib

            self.url_hash = hashlib.sha256(self.url.encode()).hexdigest()
        super().save(*args, **kwargs)


class UserArticle(models.Model):
    """Junction table linking users to globally-stored articles."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_articles"
    )
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="user_articles"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_articles"
        unique_together = ("user", "article")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user} ↔ {self.article}"
