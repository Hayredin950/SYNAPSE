from django.contrib import admin

from .models import ResearchPaper


@admin.register(ResearchPaper)
class ResearchPaperAdmin(admin.ModelAdmin):
    list_display = ["title", "difficulty_level", "citation_count", "published_date"]
    list_filter = ["difficulty_level"]
    search_fields = ["title", "abstract", "arxiv_id"]
    ordering = ["-published_date"]
