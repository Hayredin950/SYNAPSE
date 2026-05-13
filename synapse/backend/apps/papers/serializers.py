from rest_framework import serializers

from .models import ResearchPaper


class ResearchPaperSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearchPaper
        fields = [
            "id",
            "arxiv_id",
            "title",
            "abstract",
            "summary",
            "authors",
            "categories",
            "published_date",
            "url",
            "pdf_url",
            "citation_count",
            "difficulty_level",
            "key_contributions",
            "applications",
            "fetched_at",
        ]
