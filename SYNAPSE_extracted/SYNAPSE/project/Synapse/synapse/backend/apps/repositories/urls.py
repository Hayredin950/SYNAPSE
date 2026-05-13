from django.urls import path

from . import views

urlpatterns = [
    path("", views.RepositoryListView.as_view(), name="repo-list"),
    path("trending/", views.TrendingRepositoryListView.as_view(), name="repo-trending"),
    # ── TASK-602-B3: GitHub Intelligence ─────────────────────────────────────
    path(
        "trending-velocity/",
        views.GitHubTrendingView.as_view(),
        name="github-trending-velocity",
    ),
    path(
        "ecosystem/<str:language>/",
        views.GitHubEcosystemView.as_view(),
        name="github-ecosystem",
    ),
    path(
        "<uuid:pk>/analysis/",
        views.GitHubRepoAnalysisView.as_view(),
        name="github-repo-analysis",
    ),
    path("<uuid:pk>/", views.RepositoryDetailView.as_view(), name="repo-detail"),
]
