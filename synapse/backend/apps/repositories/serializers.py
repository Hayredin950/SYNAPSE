from rest_framework import serializers

from .models import Repository


class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = [
            "id",
            "github_id",
            "name",
            "full_name",
            "description",
            "url",
            "stars",
            "forks",
            "watchers",
            "open_issues",
            "language",
            "topics",
            "owner",
            "is_trending",
            "stars_today",
            "stars_7d_delta",
            "velocity_7d",
            "trend_class",
            "is_rising_star",
            "readme_summary",
            "scraped_at",
            "repo_created_at",
            "metadata",
        ]
