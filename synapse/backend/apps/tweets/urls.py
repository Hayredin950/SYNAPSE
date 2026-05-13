from django.urls import path

from . import views

urlpatterns = [
    path("", views.TweetListView.as_view(), name="tweet-list"),
    path("<uuid:pk>/", views.TweetDetailView.as_view(), name="tweet-detail"),
    path("trending/", views.TrendingTweetListView.as_view(), name="tweet-trending"),
    path("topics/", views.tweet_topics, name="tweet-topics"),
    path("search/", views.tweet_search, name="tweet-search"),
]
