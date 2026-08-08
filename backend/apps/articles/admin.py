from django.contrib import admin

from .models import Article, Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "source_type",
        "is_active",
        "scrape_interval_minutes",
        "last_scraped_at",
    ]
    list_filter = ["source_type", "is_active"]
    search_fields = ["name", "url"]


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "source",
        "topic",
        "trending_score",
        "view_count",
        "published_at",
    ]
    list_filter = ["topic", "source__source_type"]
    search_fields = ["title", "summary", "url"]
    ordering = ["-published_at"]
    readonly_fields = ["scraped_at", "url_hash", "embedding_id"]
