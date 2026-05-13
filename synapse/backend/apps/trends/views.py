"""
Trends app views — Technology Trend Radar (Phase 2 / dashboard widget).
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import TechnologyTrend
from .serializers import TechnologyTrendSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def trend_list(request):
    """
    GET /api/v1/trends/
    Returns top technology trends, optionally filtered by category or date range.
    Query params:
      - category: filter by category string
      - days: number of days back to look (default 30)
      - limit: max results (default 20)
    """
    try:
        days = max(1, min(int(request.query_params.get("days", 30)), 365))
    except (ValueError, TypeError):
        days = 30
    try:
        limit = max(1, min(int(request.query_params.get("limit", 20)), 100))
    except (ValueError, TypeError):
        limit = 20
    category = request.query_params.get("category", "")

    since = timezone.now().date() - timedelta(days=days)
    qs = TechnologyTrend.objects.filter(date__gte=since)

    if category:
        qs = qs.filter(category__icontains=category)

    # Deduplicate: one row per technology — pick the record with the highest trend_score.
    # Use a subquery to find the pk of the best-scored record per technology.
    from django.db.models import Max, OuterRef, Subquery

    best_pk_subquery = (
        TechnologyTrend.objects.filter(
            technology_name=OuterRef("technology_name"), date__gte=since
        )
        .order_by("-trend_score")
        .values("pk")[:1]
    )
    if category:
        best_pk_subquery = (
            TechnologyTrend.objects.filter(
                technology_name=OuterRef("technology_name"),
                date__gte=since,
                category__icontains=category,
            )
            .order_by("-trend_score")
            .values("pk")[:1]
        )

    top_per_tech = (
        qs.values("technology_name")
        .annotate(max_score=Max("trend_score"), best_pk=Subquery(best_pk_subquery))
        .order_by("-max_score")[:limit]
    )
    best_pks = [row["best_pk"] for row in top_per_tech if row["best_pk"]]
    results = list(
        TechnologyTrend.objects.filter(pk__in=best_pks).order_by("-trend_score")
    )

    serializer = TechnologyTrendSerializer(results, many=True)
    return Response(
        {
            "success": True,
            "count": len(serializer.data),
            "results": serializer.data,
        }
    )


@api_view(["POST"])
def trend_trigger(request):
    """
    POST /api/v1/trends/trigger/
    Manually trigger the trend analysis Celery task.
    Authenticated users only.
    """
    try:
        from .tasks import analyze_trends_task

        analyze_trends_task.delay()
        return Response({"success": True, "message": "Trend analysis task queued."})
    except Exception as exc:
        return Response(
            {"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def trend_detail(request, pk):
    """GET /api/v1/trends/<pk>/"""
    try:
        trend = TechnologyTrend.objects.get(pk=pk)
    except TechnologyTrend.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(TechnologyTrendSerializer(trend).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def trend_history(request):
    """
    GET /api/v1/trends/history/
    Returns score-over-time data for the top N technologies.

    Query params:
      - top: number of top technologies to track (default 8, max 20)
      - days: lookback window in days (default 30, max 90)

    Returns:
      {
        "technologies": ["Python", "TypeScript", ...],
        "dates": ["2026-03-28", "2026-03-29", ...],
        "series": [
          {"name": "Python", "data": [85.0, 92.0, ...]},
          ...
        ]
      }
    """
    try:
        top = max(1, min(int(request.query_params.get("top", 8)), 20))
    except (ValueError, TypeError):
        top = 8
    try:
        days = max(1, min(int(request.query_params.get("days", 30)), 90))
    except (ValueError, TypeError):
        days = 30

    since = timezone.now().date() - timedelta(days=days)

    # Get the top N techs by latest trend_score
    from django.db.models import Max

    top_techs = (
        TechnologyTrend.objects.filter(date__gte=since)
        .values("technology_name")
        .annotate(max_score=Max("trend_score"))
        .order_by("-max_score")[:top]
        .values_list("technology_name", flat=True)
    )
    top_techs = list(top_techs)

    if not top_techs:
        return Response({"technologies": [], "dates": [], "series": []})

    # Get all records for these techs in the date range
    qs = (
        TechnologyTrend.objects.filter(technology_name__in=top_techs, date__gte=since)
        .values("technology_name", "date", "trend_score")
        .order_by("date")
    )

    # Build a date → {tech → score} lookup
    date_set = sorted(set(str(r["date"]) for r in qs))
    tech_map: dict = {t: {} for t in top_techs}
    for r in qs:
        tech_map[r["technology_name"]][str(r["date"])] = round(r["trend_score"], 2)

    series = [
        {
            "name": tech,
            "data": [tech_map[tech].get(d, None) for d in date_set],
        }
        for tech in top_techs
    ]

    return Response(
        {
            "technologies": top_techs,
            "dates": date_set,
            "series": series,
            "success": True,
        }
    )
