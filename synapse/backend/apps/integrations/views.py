"""
backend.apps.integrations.views
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
REST API views for cloud integrations.

Phase 6.1 — Google Drive (Week 17)
Phase 6.2 — AWS S3 (Week 18)

Endpoints mounted at /api/v1/integrations/
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from apps.documents.models import GeneratedDocument

from django.conf import settings
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import GoogleDriveToken
from .serializers import (
    DriveListSerializer,
    DriveUploadSerializer,
    GoogleDriveStatusSerializer,
    S3PresignedUrlSerializer,
    S3UploadSerializer,
)

logger = logging.getLogger(__name__)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6.1 — Google Drive
# ═══════════════════════════════════════════════════════════════════════════════


class DriveConnectView(APIView):
    """
    GET /api/v1/integrations/drive/connect/
    Redirect the authenticated user to Google's OAuth2 consent screen.

    Returns 503 with {not_configured: true} when GOOGLE_CLIENT_ID / SECRET
    are not set so the frontend can show a "not configured" message instead
    of redirecting to a broken OAuth URL.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from .google_drive import (
            GOOGLE_CLIENT_ID,
            GOOGLE_CLIENT_SECRET,
            get_oauth2_authorization_url,
        )

        # Detect missing credentials before attempting OAuth flow
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            return Response(
                {
                    "error": "Google Drive integration is not configured on this server. "
                    "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.",
                    "not_configured": True,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        state = str(request.user.id)
        try:
            url = get_oauth2_authorization_url(state=state)
            return Response({"authorization_url": url})
        except Exception as exc:
            logger.error("Drive OAuth2 URL error: %s", exc)
            return Response(
                {
                    "error": "Could not build authorization URL. Check GOOGLE_CLIENT_ID/SECRET."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DriveCallbackView(APIView):
    """
    GET /api/v1/integrations/drive/callback/
    Google redirects here after user grants/denies permission.
    Exchanges auth code for tokens and stores them encrypted.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        code = request.query_params.get("code")
        state = request.query_params.get("state")  # user UUID
        error = request.query_params.get("error")

        if error:
            return redirect(f"{FRONTEND_URL}/dashboard?drive_error={error}")

        if not code:
            return Response(
                {"error": "Missing authorization code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from apps.users.models import User

            from .google_drive import exchange_code_for_credentials, get_user_email

            credentials_dict = exchange_code_for_credentials(code)

            # Resolve user from state (user UUID)
            user = None
            if state:
                try:
                    user = User.objects.get(id=state)
                except User.DoesNotExist:
                    pass

            if not user:
                return Response(
                    {"error": "Invalid state parameter."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            google_email = get_user_email(credentials_dict)

            token_obj, _ = GoogleDriveToken.objects.get_or_create(user=user)
            token_obj.set_credentials(credentials_dict)
            token_obj.google_email = google_email
            token_obj.save()

            logger.info("Drive connected for user %s (%s)", user.email, google_email)
            return redirect(f"{FRONTEND_URL}/dashboard/documents?drive_connected=true")

        except Exception as exc:
            logger.error("Drive callback error: %s", exc)
            return redirect(f"{FRONTEND_URL}/dashboard?drive_error=callback_failed")


class DriveDisconnectView(APIView):
    """
    DELETE /api/v1/integrations/drive/disconnect/
    Revoke and delete the stored Drive token for the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request) -> Response:
        try:
            token = GoogleDriveToken.objects.get(user=request.user)
            token.delete()
            return Response({"success": True, "message": "Google Drive disconnected."})
        except GoogleDriveToken.DoesNotExist:
            return Response(
                {"error": "No Drive account connected."},
                status=status.HTTP_404_NOT_FOUND,
            )


class DriveStatusView(APIView):
    """
    GET /api/v1/integrations/drive/status/
    Returns Drive connection status for the current user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        try:
            token = GoogleDriveToken.objects.get(user=request.user)
            return Response(
                {
                    "is_connected": True,
                    "google_email": token.google_email,
                    "connected_at": token.connected_at,
                }
            )
        except GoogleDriveToken.DoesNotExist:
            return Response(
                {"is_connected": False, "google_email": None, "connected_at": None}
            )


class DriveUploadView(APIView):
    """
    POST /api/v1/integrations/drive/upload/
    Upload a GeneratedDocument file to the user's Google Drive.

    Body: { document_id: UUID, folder_name: str }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = DriveUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        document_id = serializer.validated_data["document_id"]
        folder_name = serializer.validated_data["folder_name"]

        # Get Drive token
        try:
            token = GoogleDriveToken.objects.get(user=request.user)
        except GoogleDriveToken.DoesNotExist:
            return Response(
                {
                    "error": "Google Drive not connected. Visit /integrations/drive/connect/ first."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get document
        try:
            doc = GeneratedDocument.objects.get(id=document_id, user=request.user)
        except GeneratedDocument.DoesNotExist:
            return Response(
                {"error": "Document not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not doc.file_path:
            return Response(
                {"error": "Document has no associated file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        abs_path = Path(settings.MEDIA_ROOT) / doc.file_path
        if not abs_path.exists():
            return Response(
                {"error": "File not found on server."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            from .google_drive import upload_to_drive

            credentials_dict = token.get_credentials()
            result = upload_to_drive(
                file_path=str(abs_path),
                folder_name=folder_name,
                credentials_dict=credentials_dict,
            )

            # Store Drive URL in cloud_url field
            doc.cloud_url = result.get("webViewLink", "")
            doc.metadata["drive_file_id"] = result.get("id", "")
            doc.metadata["drive_folder"] = folder_name
            doc.save(update_fields=["cloud_url", "metadata"])

            return Response(
                {
                    "success": True,
                    "drive_file_id": result.get("id"),
                    "drive_url": result.get("webViewLink"),
                    "file_name": result.get("name"),
                }
            )
        except FileNotFoundError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.error("Drive upload error: %s", exc)
            return Response(
                {"error": f"Upload failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DriveListFilesView(APIView):
    """
    GET /api/v1/integrations/drive/files/?folder_name=SYNAPSE+Documents
    List files in a Drive folder.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        folder_name = request.query_params.get("folder_name", "SYNAPSE Documents")

        try:
            token = GoogleDriveToken.objects.get(user=request.user)
        except GoogleDriveToken.DoesNotExist:
            return Response(
                {"error": "Google Drive not connected."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            from .google_drive import list_drive_files

            credentials_dict = token.get_credentials()
            files = list_drive_files(
                folder_name=folder_name, credentials_dict=credentials_dict
            )
            return Response(
                {"folder_name": folder_name, "files": files, "count": len(files)}
            )
        except Exception as exc:
            logger.error("Drive list error: %s", exc)
            return Response(
                {"error": f"Could not list files: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DriveCreateFolderView(APIView):
    """
    POST /api/v1/integrations/drive/folders/
    Create a folder in the user's Google Drive.

    Body: { folder_name: str }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        folder_name = request.data.get("folder_name", "").strip()
        if not folder_name:
            return Response(
                {"error": "folder_name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = GoogleDriveToken.objects.get(user=request.user)
        except GoogleDriveToken.DoesNotExist:
            return Response(
                {"error": "Google Drive not connected."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            from .google_drive import create_drive_folder

            credentials_dict = token.get_credentials()
            folder_id = create_drive_folder(
                folder_name=folder_name, credentials_dict=credentials_dict
            )
            return Response(
                {"success": True, "folder_name": folder_name, "folder_id": folder_id}
            )
        except Exception as exc:
            logger.error("Drive create folder error: %s", exc)
            return Response(
                {"error": f"Could not create folder: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DriveExportAsGoogleDocView(APIView):
    """
    POST /api/v1/integrations/drive/export-as-doc/
    Upload a Word/DOCX document to Google Drive and convert it to a native Google Doc.
    Body: { document_id: UUID, folder_name?: str }
    Returns: { google_doc_id, google_doc_url, file_name }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        document_id = request.data.get("document_id")
        folder_name = request.data.get("folder_name", "SYNAPSE Documents")

        if not document_id:
            return Response(
                {"error": "document_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = GoogleDriveToken.objects.get(user=request.user)
        except GoogleDriveToken.DoesNotExist:
            return Response(
                {"error": "Google Drive not connected."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            doc = GeneratedDocument.objects.get(id=document_id, user=request.user)
        except GeneratedDocument.DoesNotExist:
            return Response(
                {"error": "Document not found."}, status=status.HTTP_404_NOT_FOUND
            )

        abs_path = Path(settings.MEDIA_ROOT) / doc.file_path if doc.file_path else None
        if not abs_path or not abs_path.exists():
            return Response(
                {"error": "File not found on server."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            from .google_drive import export_as_google_doc

            credentials_dict = token.get_credentials()
            result = export_as_google_doc(
                file_path=str(abs_path),
                folder_name=folder_name,
                credentials_dict=credentials_dict,
                doc_title=doc.title,
            )
            # Store result
            doc.metadata["google_doc_id"] = result.get("id", "")
            doc.metadata["google_doc_url"] = result.get("webViewLink", "")
            doc.cloud_url = result.get("webViewLink", "")
            doc.save(update_fields=["cloud_url", "metadata"])
            return Response(
                {
                    "success": True,
                    "google_doc_id": result.get("id"),
                    "google_doc_url": result.get("webViewLink"),
                    "file_name": result.get("name"),
                }
            )
        except Exception as exc:
            logger.error("Google Docs export error: %s", exc)
            return Response(
                {"error": f"Export failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6.2 — AWS S3
# ═══════════════════════════════════════════════════════════════════════════════


class S3UploadView(APIView):
    """
    POST /api/v1/integrations/s3/upload/
    Upload a GeneratedDocument file to AWS S3.

    Body: { document_id: UUID, bucket?: str, prefix?: str }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = S3UploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        document_id = serializer.validated_data["document_id"]
        bucket = serializer.validated_data.get("bucket") or None
        prefix = serializer.validated_data.get("prefix", "documents/")

        try:
            doc = GeneratedDocument.objects.get(id=document_id, user=request.user)
        except GeneratedDocument.DoesNotExist:
            return Response(
                {"error": "Document not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not doc.file_path:
            return Response(
                {"error": "Document has no associated file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        abs_path = Path(settings.MEDIA_ROOT) / doc.file_path
        if not abs_path.exists():
            return Response(
                {"error": "File not found on server."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            from .s3 import (
                AWS_ACCESS_KEY_ID,
                AWS_S3_BUCKET_NAME,
                AWS_SECRET_ACCESS_KEY,
                upload_to_s3,
            )

            if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
                return Response(
                    {
                        "error": "AWS S3 is not configured on this server. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables."
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            if not AWS_S3_BUCKET_NAME:
                return Response(
                    {
                        "error": "AWS S3 bucket is not configured. Set AWS_STORAGE_BUCKET_NAME environment variable."
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            target_bucket = bucket or AWS_S3_BUCKET_NAME
            key = f"{prefix.rstrip('/')}/{abs_path.name}"

            result = upload_to_s3(str(abs_path), bucket=target_bucket, key=key)

            # Update cloud_url with presigned URL
            doc.cloud_url = result["presigned_url"]
            doc.metadata["s3_bucket"] = target_bucket
            doc.metadata["s3_key"] = key
            doc.save(update_fields=["cloud_url", "metadata"])

            return Response(
                {
                    "success": True,
                    "bucket": result["bucket"],
                    "key": result["key"],
                    "presigned_url": result["presigned_url"],
                    "url": result["url"],
                }
            )
        except FileNotFoundError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.error("S3 upload error: %s", exc)
            return Response(
                {"error": f"S3 upload failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class S3PresignedUrlView(APIView):
    """
    POST /api/v1/integrations/s3/presigned-url/
    Generate a fresh presigned URL for a document already on S3.

    Body: { document_id: UUID, expiry_seconds?: int }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = S3PresignedUrlSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        document_id = serializer.validated_data["document_id"]
        expiry_seconds = serializer.validated_data["expiry_seconds"]

        try:
            doc = GeneratedDocument.objects.get(id=document_id, user=request.user)
        except GeneratedDocument.DoesNotExist:
            return Response(
                {"error": "Document not found."}, status=status.HTTP_404_NOT_FOUND
            )

        s3_key = doc.metadata.get("s3_key")
        s3_bucket = doc.metadata.get("s3_bucket")

        if not s3_key or not s3_bucket:
            return Response(
                {"error": "Document is not stored on S3."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from .s3 import get_presigned_url

            url = get_presigned_url(
                bucket=s3_bucket, key=s3_key, expiry_seconds=expiry_seconds
            )

            # Refresh stored cloud_url
            doc.cloud_url = url
            doc.save(update_fields=["cloud_url"])

            return Response(
                {
                    "success": True,
                    "presigned_url": url,
                    "expiry_seconds": expiry_seconds,
                }
            )
        except Exception as exc:
            logger.error("Presigned URL error: %s", exc)
            return Response(
                {"error": f"Could not generate presigned URL: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ── TASK-607: Integration connect/status/disconnect views ─────────────────────


class NotionConnectView(APIView):
    """GET /api/v1/integrations/notion/connect/ — redirect to Notion OAuth."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        import uuid

        from apps.integrations.notion import get_authorization_url  # noqa

        state = uuid.uuid4().hex
        request.session["notion_oauth_state"] = state
        url = get_authorization_url(state=str(request.user.pk))
        return Response({"success": True, "data": {"url": url}})


class NotionCallbackView(APIView):
    """POST /api/v1/integrations/notion/callback/ — exchange code for token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.integrations.notion import exchange_code_for_token  # noqa

        code = request.data.get("code", "")
        if not code:
            return Response({"success": False, "error": "Missing code"}, status=400)
        try:
            token_data = exchange_code_for_token(code)
            # Store token in user integration metadata (simplified — use encrypted storage in prod)
            request.user.notion_token = token_data.get("access_token", "")
            if hasattr(request.user, "save"):
                (
                    request.user.save(update_fields=[]) if False else None
                )  # no-op: store in cache instead
            # In production, store in IntegrationToken model
            from django.core.cache import cache

            cache.set(
                f"notion_token:{request.user.pk}",
                token_data.get("access_token", ""),
                timeout=None,
            )
            workspace = token_data.get("workspace_name", "Your workspace")
            return Response({"success": True, "data": {"workspace": workspace}})
        except Exception as exc:
            return Response({"success": False, "error": str(exc)}, status=400)


class NotionStatusView(APIView):
    """GET /api/v1/integrations/notion/status/ — connection status."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.core.cache import cache

        token = cache.get(f"notion_token:{request.user.pk}")
        return Response({"success": True, "data": {"connected": bool(token)}})


class NotionDisconnectView(APIView):
    """POST /api/v1/integrations/notion/disconnect/ — revoke token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.core.cache import cache

        cache.delete(f"notion_token:{request.user.pk}")
        return Response({"success": True, "data": {"message": "Notion disconnected"}})


class SlackConnectView(APIView):
    """GET /api/v1/integrations/slack/connect/ — redirect to Slack OAuth."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.integrations.slack import get_authorization_url  # noqa

        url = get_authorization_url(state=str(request.user.pk))
        return Response({"success": True, "data": {"url": url}})


class SlackStatusView(APIView):
    """GET /api/v1/integrations/slack/status/ — connection status."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.core.cache import cache

        token = cache.get(f"slack_token:{request.user.pk}")
        return Response({"success": True, "data": {"connected": bool(token)}})


class SlackDisconnectView(APIView):
    """POST /api/v1/integrations/slack/disconnect/ — revoke."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.core.cache import cache

        cache.delete(f"slack_token:{request.user.pk}")
        return Response({"success": True, "data": {"message": "Slack disconnected"}})


class SlackSlashCommandView(APIView):
    """POST /api/v1/integrations/slack/slash/ — handle /synapse slash command."""

    permission_classes = [AllowAny]  # Slack calls this without JWT

    def post(self, request):
        from apps.integrations.slack import (  # noqa
            handle_slash_command,
            verify_slack_signature,
        )

        # Verify signature
        body = request.body
        timestamp = request.META.get("HTTP_X_SLACK_REQUEST_TIMESTAMP", "")
        signature = request.META.get("HTTP_X_SLACK_SIGNATURE", "")
        if not verify_slack_signature(body, timestamp, signature):
            return Response({"error": "Invalid signature"}, status=403)
        # Parse URL-encoded Slack payload
        import urllib.parse

        payload = dict(urllib.parse.parse_qsl(body.decode()))
        result = handle_slash_command(payload)
        return Response(result)


class ObsidianImportView(APIView):
    """POST /api/v1/integrations/obsidian/import/ — upload and parse vault files."""

    permission_classes = [IsAuthenticated]
    from rest_framework.parsers import MultiPartParser

    parser_classes = [MultiPartParser]

    def post(self, request):
        from apps.integrations.obsidian import (  # noqa
            import_vault_notes,
            parse_markdown_file,
        )

        files = request.FILES.getlist("files")
        if not files:
            return Response(
                {"success": False, "error": "No files uploaded"}, status=400
            )

        notes = []
        for f in files[:100]:  # limit to 100 files per upload
            try:
                content = f.read().decode("utf-8", errors="replace")
                note = parse_markdown_file(f.name, content)
                notes.append(note)
            except Exception as exc:
                logger.warning("Failed to parse Obsidian file %s: %s", f.name, exc)

        result = import_vault_notes(notes, request.user)
        return Response({"success": True, "data": result}, status=201)


class ZoteroConnectView(APIView):
    """POST /api/v1/integrations/zotero/connect/ — validate + store API key."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.integrations.zotero import ZoteroClient, import_library  # noqa

        api_key = (request.data.get("api_key") or "").strip()
        user_id = (request.data.get("user_id") or "").strip()
        if not api_key or not user_id:
            return Response(
                {"success": False, "error": "api_key and user_id are required"},
                status=400,
            )

        client = ZoteroClient(api_key=api_key, user_id=user_id)
        if not client.validate_credentials():
            return Response(
                {"success": False, "error": "Invalid Zotero credentials"}, status=400
            )

        # Store in cache (use encrypted model in production)
        from django.core.cache import cache

        cache.set(
            f"zotero_config:{request.user.pk}",
            {"api_key": api_key, "user_id": user_id},
            timeout=None,
        )

        # Kick off background import
        try:
            from apps.core.tasks import import_zotero_library  # noqa

            import_zotero_library.delay(str(request.user.pk), api_key, user_id)
        except Exception as exc:
            logger.warning("Could not enqueue Zotero import: %s", exc)

        return Response(
            {
                "success": True,
                "data": {
                    "message": "Zotero connected. Importing library in background…"
                },
            }
        )


class ZoteroStatusView(APIView):
    """GET /api/v1/integrations/zotero/status/ — connection status."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.core.cache import cache

        config = cache.get(f"zotero_config:{request.user.pk}")
        return Response({"success": True, "data": {"connected": bool(config)}})


class ZoteroDisconnectView(APIView):
    """POST /api/v1/integrations/zotero/disconnect/ — remove config."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.core.cache import cache

        cache.delete(f"zotero_config:{request.user.pk}")
        return Response({"success": True, "data": {"message": "Zotero disconnected"}})
