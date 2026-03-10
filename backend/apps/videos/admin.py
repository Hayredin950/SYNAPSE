from django.contrib import admin

from .models import Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ["title", "channel_name", "view_count", "published_at"]
    search_fields = ["title", "channel_name", "youtube_id"]
    ordering = ["-published_at"]
