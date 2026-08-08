from django.contrib import admin

from .models import Tweet


@admin.register(Tweet)
class TweetAdmin(admin.ModelAdmin):
    list_display = [
        "author_username",
        "text",
        "like_count",
        "retweet_count",
        "topic",
        "posted_at",
    ]
    list_filter = ["topic", "lang", "is_retweet", "is_reply"]
    search_fields = ["text", "author_username", "author_display_name"]
    ordering = ["-posted_at"]
    readonly_fields = ["scraped_at", "tweet_id"]
