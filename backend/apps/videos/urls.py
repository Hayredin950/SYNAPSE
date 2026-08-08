from django.urls import path

from . import views

urlpatterns = [
    path("", views.VideoListView.as_view(), name="video-list"),
    path("<uuid:pk>/", views.VideoDetailView.as_view(), name="video-detail"),
    path("trending/", views.TrendingVideoListView.as_view(), name="video-trending"),
]
