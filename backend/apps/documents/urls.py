"""
backend.apps.documents.urls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
URL routing for Document Studio.

Phase 5.2 — Document Generation (Week 14)
Phase 5.3 — Project Builder (Week 15)

Mounted at: /api/v1/documents/
"""

from django.urls import path

from . import views

urlpatterns = [
    # Generate a new document (PDF, PPT, Word, Markdown)
    path("generate/", views.DocumentGenerateView.as_view(), name="document-generate"),
    # Generate a project scaffold (.zip) — Phase 5.3
    path(
        "generate-project/",
        views.ProjectGenerateView.as_view(),
        name="project-generate",
    ),
    # List all user documents
    path("", views.DocumentListView.as_view(), name="document-list"),
    # Document detail + delete
    path("<uuid:doc_id>/", views.DocumentDetailView.as_view(), name="document-detail"),
    # File download (works for all types including .zip projects)
    path(
        "<uuid:doc_id>/download/",
        views.DocumentDownloadView.as_view(),
        name="document-download",
    ),
    # Document preview (PNG thumbnail)
    path(
        "<str:doc_id>/preview/",
        views.DocumentPreviewView.as_view(),
        name="document-preview",
    ),
    path(
        "<str:doc_id>/render/",
        views.DocumentRenderView.as_view(),
        name="document-render",
    ),
    # Regenerate a single section
    path(
        "<str:doc_id>/regenerate-section/",
        views.DocumentSectionRegenerateView.as_view(),
        name="document-section-regenerate",
    ),
    # Update multiple sections and rebuild document
    path(
        "<str:doc_id>/update-sections/",
        views.DocumentSectionsUpdateView.as_view(),
        name="document-update-sections",
    ),
    # Regenerate all sections and rebuild document
    path(
        "<str:doc_id>/regenerate-all/",
        views.DocumentRegenerateAllView.as_view(),
        name="document-regenerate-all",
    ),
    # Get version history
    path(
        "<str:doc_id>/versions/",
        views.DocumentVersionsView.as_view(),
        name="document-versions",
    ),
    # Server-Sent Events (SSE) streaming endpoint for document generation
    path(
        "generate-stream/",
        views.DocumentGenerateStreamView.as_view(),
        name="document-generate-stream",
    ),
]
