from rest_framework import serializers

from .models import TechnologyTrend


class TechnologyTrendSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnologyTrend
        fields = [
            "id",
            "technology_name",
            "mention_count",
            "trend_score",
            "category",
            "date",
            "sources",
        ]
