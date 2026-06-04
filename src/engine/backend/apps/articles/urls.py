from django.urls import path

from . import views

urlpatterns = [
    path("", views.ArticleListView.as_view(), name="article-list"),
    path("<uuid:pk>/", views.ArticleDetailView.as_view(), name="article-detail"),
    path("trending/", views.TrendingArticleListView.as_view(), name="article-trending"),
    path("topics/", views.article_topics, name="article-topics"),
    path("search/", views.article_search, name="article-search"),
    # Trigger summarization manually (called by frontend on feed load)
    path("summarize/", views.trigger_summarization, name="article-summarize"),
]
