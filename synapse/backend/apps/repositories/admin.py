from django.contrib import admin

from .models import Repository


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "language",
        "stars",
        "forks",
        "is_trending",
        "scraped_at",
    ]
    list_filter = ["language", "is_trending"]
    search_fields = ["name", "full_name", "description", "owner"]
    ordering = ["-stars"]
