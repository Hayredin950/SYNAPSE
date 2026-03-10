"""
TASK-605-B3: Public API URL routes.

Mounted at:
  /api/v1/content/   → articles, papers, repos, save
  /api/v1/ai/        → AI query
  /api/v1/trends/    → trending

All use APIKeyAuthentication + IsAuthenticated + APIRateThrottle.
"""

from django.urls import path

from .public_api_views import (
    PublicAIQueryView,
    PublicArticlesView,
    PublicPapersView,
    PublicReposView,
    PublicSaveContentView,
    PublicTrendsView,
)

urlpatterns = [
    # Content endpoints
    path("articles/", PublicArticlesView.as_view(), name="public-articles"),
    path("papers/", PublicPapersView.as_view(), name="public-papers"),
    path("repos/", PublicReposView.as_view(), name="public-repos"),
    path("save/", PublicSaveContentView.as_view(), name="public-save"),
    # AI query
    path("query/", PublicAIQueryView.as_view(), name="public-ai-query"),
    # Trends (also mounted at /api/v1/trends/ top-level)
    path("", PublicTrendsView.as_view(), name="public-trends"),
]
