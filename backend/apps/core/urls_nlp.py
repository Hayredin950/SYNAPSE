"""
URL patterns for NLP / AI on-demand endpoints.

Mounted at /api/v1/ai/ by config/urls.py.
"""

from django.urls import path

from . import views_chat, views_nlp, views_ai

urlpatterns = [
    # Phase 2.1 — NLP
    path("summarize/", views_nlp.summarize_text, name="ai-summarize"),
    path("nlp/", views_nlp.analyze_text, name="ai-nlp-analyze"),
    path(
        "process/<uuid:article_id>/",
        views_nlp.trigger_article_nlp,
        name="ai-process-article",
    ),
    # Phase 2.3 — Embeddings
    path(
        "embed/article/<uuid:article_id>/",
        views_nlp.trigger_article_embedding,
        name="ai-embed-article",
    ),
    path(
        "embed/paper/<uuid:paper_id>/",
        views_nlp.trigger_paper_embedding,
        name="ai-embed-paper",
    ),
    path(
        "embed/repo/<uuid:repo_id>/",
        views_nlp.trigger_repo_embedding,
        name="ai-embed-repo",
    ),
    path(
        "embed/video/<uuid:video_id>/",
        views_nlp.trigger_video_embedding,
        name="ai-embed-video",
    ),
    path("embed/batch/", views_nlp.trigger_batch_embeddings, name="ai-embed-batch"),
    # Phase 3.1 — RAG Chat
    path("explain/", views_chat.ExplainView.as_view(), name="ai-explain"),
    path("chat/transcribe/", views_chat.TranscribeView.as_view(), name="ai-transcribe"),
    path("chat/", views_chat.ChatView.as_view(), name="ai-chat"),
    path(
        "chat/<str:conversation_id>/messages/<int:index>/",
        views_chat.MessageDeleteView.as_view(),
        name="ai-message-delete",
    ),
    path("chat/stream/", views_chat.ChatStreamView.as_view(), name="ai-chat-stream"),
    path(
        "chat/conversations/",
        views_chat.ConversationListView.as_view(),
        name="ai-conversations",
    ),
    path(
        "chat/<str:conversation_id>/history/",
        views_chat.ConversationHistoryView.as_view(),
        name="ai-chat-history",
    ),
    path(
        "chat/<str:conversation_id>/",
        views_chat.ConversationDeleteView.as_view(),
        name="ai-conversation-delete",
    ),

    # ── 40-Feature Pack: AI Features ─────────────────────────────────────────
    path("debate/",        views_ai.debate_mode,       name="ai-debate"),
    path("translate/",     views_ai.translate_article,  name="ai-translate"),
    path("paper-to-blog/", views_ai.paper_to_blog,      name="ai-paper-to-blog"),
    path("catch-up/",      views_ai.catch_me_up,        name="ai-catch-up"),
    path("research/",      views_ai.research_brief,     name="ai-research"),
    path("tts/",           views_ai.text_to_speech,     name="ai-tts"),
    path("podcast/",       views_ai.generate_podcast,   name="ai-podcast"),
    path("code-extract/",  views_ai.code_extract,       name="ai-code-extract"),
    path("related/",       views_ai.related_articles,   name="ai-related"),
    path("deep-dive/",     views_ai.deep_dive,           name="ai-deep-dive"),
]
