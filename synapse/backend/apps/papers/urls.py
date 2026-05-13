from django.urls import path

from . import views

urlpatterns = [
    path("", views.PaperListView.as_view(), name="paper-list"),
    path("<uuid:pk>/", views.PaperDetailView.as_view(), name="paper-detail"),
    path("trending/", views.TrendingPaperListView.as_view(), name="paper-trending"),
]
