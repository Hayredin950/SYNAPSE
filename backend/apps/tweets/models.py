import uuid

from pgvector.django import VectorField

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone


class Tweet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tweet_id = models.CharField(max_length=50, unique=True, db_index=True)
    text = models.TextField()
    author_username = models.CharField(max_length=200, db_index=True)
    author_display_name = models.CharField(max_length=300, blank=True)
    author_profile_image = models.URLField(max_length=500, blank=True)
    author_verified = models.BooleanField(default=False)
    author_followers = models.IntegerField(default=0)
    retweet_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)
    reply_count = models.IntegerField(default=0)
    quote_count = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)
    bookmark_count = models.IntegerField(default=0)
    posted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    scraped_at = models.DateTimeField(default=timezone.now, db_index=True)
    hashtags = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    mentions = ArrayField(models.CharField(max_length=200), default=list, blank=True)
    media_urls = ArrayField(models.URLField(max_length=1000), default=list, blank=True)
    urls = ArrayField(models.URLField(max_length=1000), default=list, blank=True)
    is_retweet = models.BooleanField(default=False)
    is_reply = models.BooleanField(default=False)
    is_quote = models.BooleanField(default=False)
    conversation_id = models.CharField(max_length=50, blank=True, db_index=True)
    in_reply_to_user = models.CharField(max_length=200, blank=True)
    lang = models.CharField(max_length=10, blank=True)
    url = models.URLField(max_length=500, blank=True)
    source_label = models.CharField(max_length=200, blank=True)
    topic = models.CharField(max_length=100, blank=True, db_index=True)
    trending_score = models.FloatField(default=0.0, db_index=True)
    sentiment_score = models.FloatField(null=True, blank=True)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tweets"
        ordering = ["-posted_at", "-scraped_at"]
        indexes = [
            models.Index(fields=["trending_score"]),
            models.Index(fields=["posted_at"]),
            models.Index(fields=["author_username"]),
            models.Index(fields=["topic"]),
        ]

    def __str__(self):
        return f"@{self.author_username}: {self.text[:60]}"

    def save(self, *args, **kwargs):
        if not self.url and self.tweet_id:
            self.url = f"https://x.com/{self.author_username}/status/{self.tweet_id}"
        super().save(*args, **kwargs)


class UserTweet(models.Model):
    """Junction table linking users to globally-stored tweets."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_tweets"
    )
    tweet = models.ForeignKey(
        Tweet, on_delete=models.CASCADE, related_name="user_tweets"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_tweets"
        unique_together = ("user", "tweet")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user} ↔ {self.tweet}"
