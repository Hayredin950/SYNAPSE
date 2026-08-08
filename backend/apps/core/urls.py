from django.urls import path

from . import views, views_stream, views_social

urlpatterns = [
    path("health/", views.health_check, name="health-check"),
    # ── TASK-305-B3: Daily Briefing ──────────────────────────────────────────
    path("briefing/today/", views.TodayBriefingView.as_view(), name="briefing-today"),
    # TASK-601-B4: PDF export for research reports
    path(
        "research/<uuid:pk>/export-pdf/",
        views.ResearchReportPDFView.as_view(),
        name="research-export-pdf",
    ),
    path(
        "briefing/history/",
        views.BriefingHistoryView.as_view(),
        name="briefing-history",
    ),
    # ── TASK-603-B3: Knowledge Graph ──────────────────────────────────────────
    path(
        "knowledge-graph/", views.KnowledgeGraphView.as_view(), name="knowledge-graph"
    ),
    path(
        "knowledge-graph/search/",
        views.KnowledgeGraphSearchView.as_view(),
        name="knowledge-graph-search",
    ),
    path(
        "knowledge-graph/nodes/<uuid:pk>/",
        views.KnowledgeNodeDetailView.as_view(),
        name="knowledge-node-detail",
    ),
    # ── TASK-505-B3: Audit log ────────────────────────────────────────────────
    path("audit-log/", views.AuditLogListView.as_view(), name="audit-log"),
    path("search/", views.global_search, name="global-search"),
    path("search/bm25/", views.bm25_search_view, name="bm25-search"),
    path("search/hybrid/", views.hybrid_search_view, name="hybrid-search"),
    path("search/semantic/", views.semantic_search, name="semantic-search"),
    path("scraper/run/", views.ScraperRunView.as_view(), name="scraper-run"),
    path("bookmarks/", views.BookmarkListView.as_view(), name="bookmark-list"),
    path(
        "bookmarks/<uuid:pk>/notes/",
        views.BookmarkNotesView.as_view(),
        name="bookmark-notes",
    ),
    path(
        "bookmarks/<str:content_type_name>/<str:object_id>/",
        views.BookmarkToggleView.as_view(),
        name="bookmark-toggle",
    ),
    path(
        "collections/", views.CollectionListCreateView.as_view(), name="collection-list"
    ),
    path(
        "collections/<uuid:pk>/",
        views.CollectionDetailView.as_view(),
        name="collection-detail",
    ),
    path(
        "collections/<uuid:pk>/bookmarks/",
        views.CollectionBookmarkView.as_view(),
        name="collection-bookmarks",
    ),
    path("recommendations/", views.recommendations, name="recommendations"),
    path("trending/", views.trending, name="trending"),
    path("api-status/", views.APIStatusView.as_view(), name="api-status"),
    # ── SSE real-time content stream ──────────────────────────────────────────
    path("stream/", views_stream.content_stream, name="content-stream"),

    # ── 40-Feature Pack: Social & Community ──────────────────────────────────
    path("social/upvote/",                        views_social.upvote,           name="social-upvote"),
    path("social/upvotes/",                       views_social.upvote_counts,    name="social-upvote-counts"),
    path("social/comments/",                      views_social.comments,         name="social-comments"),
    path("social/comments/<str:comment_id>/",     views_social.delete_comment,   name="social-comment-delete"),
    path("social/watchlist/",                     views_social.watchlist,        name="social-watchlist"),
    path("social/watchlist/<str:watch_id>/",      views_social.delete_watchlist, name="social-watchlist-delete"),
    path("social/digest/share/",                  views_social.share_digest,     name="social-share-digest"),
    path("social/digest/<str:share_id>/",         views_social.view_digest,      name="social-view-digest"),
    path("social/network-reading/",               views_social.network_reading,  name="social-network-reading"),
    path("social/source-quality/<str:domain>/",   views_social.source_quality,   name="social-source-quality"),
]
