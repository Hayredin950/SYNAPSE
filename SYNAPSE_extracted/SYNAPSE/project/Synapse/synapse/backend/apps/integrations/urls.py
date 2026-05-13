"""
backend.apps.integrations.urls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
URL routing for cloud integrations.

Phase 6.1 — Google Drive (Week 17)
Phase 6.2 — AWS S3 (Week 18)

Mounted at: /api/v1/integrations/
"""

from django.urls import path

from . import views

urlpatterns = [
    # ── Google Drive ────────────────────────────────────────────────────────
    # Start OAuth2 flow — returns {authorization_url}
    path("drive/connect/", views.DriveConnectView.as_view(), name="drive-connect"),
    # OAuth2 callback (Google redirects here)
    path("drive/callback/", views.DriveCallbackView.as_view(), name="drive-callback"),
    # Disconnect / revoke stored token
    path(
        "drive/disconnect/",
        views.DriveDisconnectView.as_view(),
        name="drive-disconnect",
    ),
    # Connection status for current user
    path("drive/status/", views.DriveStatusView.as_view(), name="drive-status"),
    # Upload a document to Drive
    path("drive/upload/", views.DriveUploadView.as_view(), name="drive-upload"),
    # List files in a Drive folder
    path("drive/files/", views.DriveListFilesView.as_view(), name="drive-list-files"),
    # Create a Drive folder
    path(
        "drive/folders/",
        views.DriveCreateFolderView.as_view(),
        name="drive-create-folder",
    ),
    # Export a document as a Google Doc
    path(
        "drive/export-as-doc/",
        views.DriveExportAsGoogleDocView.as_view(),
        name="drive-export-as-doc",
    ),
    # ── AWS S3 ──────────────────────────────────────────────────────────────────
    # Upload a document to S3
    path("s3/upload/", views.S3UploadView.as_view(), name="s3-upload"),
    # Generate / refresh a presigned download URL
    path(
        "s3/presigned-url/", views.S3PresignedUrlView.as_view(), name="s3-presigned-url"
    ),
]

# ── TASK-607: New Integrations ────────────────────────────────────────────────
urlpatterns += [
    # Notion
    path("notion/connect/", views.NotionConnectView.as_view(), name="notion-connect"),
    path(
        "notion/callback/", views.NotionCallbackView.as_view(), name="notion-callback"
    ),
    path("notion/status/", views.NotionStatusView.as_view(), name="notion-status"),
    path(
        "notion/disconnect/",
        views.NotionDisconnectView.as_view(),
        name="notion-disconnect",
    ),
    # Slack
    path("slack/connect/", views.SlackConnectView.as_view(), name="slack-connect"),
    path("slack/status/", views.SlackStatusView.as_view(), name="slack-status"),
    path(
        "slack/disconnect/",
        views.SlackDisconnectView.as_view(),
        name="slack-disconnect",
    ),
    path("slack/slash/", views.SlackSlashCommandView.as_view(), name="slack-slash"),
    # Obsidian
    path(
        "obsidian/import/", views.ObsidianImportView.as_view(), name="obsidian-import"
    ),
    # Zotero
    path("zotero/connect/", views.ZoteroConnectView.as_view(), name="zotero-connect"),
    path("zotero/status/", views.ZoteroStatusView.as_view(), name="zotero-status"),
    path(
        "zotero/disconnect/",
        views.ZoteroDisconnectView.as_view(),
        name="zotero-disconnect",
    ),
]
