"""
backend.apps.integrations.serializers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DRF serializers for cloud integration endpoints.

Phase 6.1 — Google Drive Integration (Week 17)
Phase 6.2 — AWS S3 Integration (Week 18)
"""

from rest_framework import serializers

from .models import GoogleDriveToken


class GoogleDriveStatusSerializer(serializers.ModelSerializer):
    """Read-only serializer for Drive connection status shown in user profile."""

    is_connected = serializers.BooleanField(read_only=True)

    class Meta:
        model = GoogleDriveToken
        fields = ["is_connected", "google_email", "connected_at", "updated_at"]
        read_only_fields = fields


class DriveUploadSerializer(serializers.Serializer):
    """Input for the upload-to-drive endpoint."""

    document_id = serializers.UUIDField(
        help_text="UUID of the GeneratedDocument to upload to Drive."
    )
    folder_name = serializers.CharField(
        max_length=200,
        default="SYNAPSE Documents",
        help_text="Drive folder name (created if it doesn't exist).",
    )


class DriveListSerializer(serializers.Serializer):
    """Input for the list-drive-files endpoint."""

    folder_name = serializers.CharField(
        max_length=200,
        default="SYNAPSE Documents",
        help_text="Drive folder name to list files from.",
    )


class S3UploadSerializer(serializers.Serializer):
    """Input for the upload-to-s3 endpoint."""

    document_id = serializers.UUIDField(
        help_text="UUID of the GeneratedDocument to upload to S3."
    )
    bucket = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        help_text="S3 bucket name (defaults to AWS_STORAGE_BUCKET_NAME env var).",
    )
    prefix = serializers.CharField(
        max_length=200,
        default="documents/",
        help_text="S3 key prefix (folder path inside bucket).",
    )


class S3PresignedUrlSerializer(serializers.Serializer):
    """Input for generating a presigned URL."""

    document_id = serializers.UUIDField(
        help_text="UUID of the GeneratedDocument stored on S3."
    )
    expiry_seconds = serializers.IntegerField(
        default=3600,
        min_value=60,
        max_value=604800,  # 7 days
        help_text="Presigned URL lifetime in seconds (60–604800).",
    )
