import uuid

from django.db import models


class TechnologyTrend(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    technology_name = models.CharField(max_length=200)
    mention_count = models.IntegerField(default=0)
    trend_score = models.FloatField(default=0.0)
    category = models.CharField(max_length=100, blank=True)
    date = models.DateField()
    sources = models.JSONField(default=list)

    class Meta:
        db_table = "technology_trends"
        ordering = ["-trend_score"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["category"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["technology_name", "date"], name="unique_trend_per_day"
            ),
        ]

    def __str__(self):
        return f"{self.technology_name} ({self.date})"
