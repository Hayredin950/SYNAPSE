"""
Tests for Phase 6 — Cloud Integrations (Google Drive + AWS S3).

These tests mock external API calls so they run without real credentials.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from apps.integrations.models import GoogleDriveToken
from apps.integrations.s3 import get_presigned_url, upload_to_s3

from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class GoogleDriveTokenModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="driveuser",
            email="drive@test.com",
            password="testpass123",
        )

    def test_set_and_get_credentials(self):
        """Credentials should encrypt on set and decrypt on get."""
        token = GoogleDriveToken(user=self.user)
        creds = {
            "token": "ya29.fake_token",
            "refresh_token": "1//fake_refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "fake-client-id",
            "client_secret": "fake-secret",
            "scopes": ["https://www.googleapis.com/auth/drive.file"],
        }
        token.set_credentials(creds)
        token.save()

        # Reload from DB
        token.refresh_from_db()
        recovered = token.get_credentials()
        self.assertEqual(recovered["token"], creds["token"])
        self.assertEqual(recovered["refresh_token"], creds["refresh_token"])

    def test_is_connected_property(self):
        token = GoogleDriveToken(user=self.user)
        self.assertFalse(token.is_connected)
        token.set_credentials({"token": "t", "refresh_token": "r"})
        self.assertTrue(token.is_connected)

    def test_str(self):
        token = GoogleDriveToken(user=self.user)
        self.assertIn("DriveToken", str(token))


class DriveStatusAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="statususer",
            email="status@test.com",
            password="testpass123",
        )
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)

    def test_drive_status_not_connected(self):
        resp = self.client.get(
            "/api/v1/integrations/drive/status/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["is_connected"])

    def test_drive_status_connected(self):
        t = GoogleDriveToken.objects.create(
            user=self.user, google_email="user@gmail.com"
        )
        t.set_credentials({"token": "x", "refresh_token": "y"})
        t.save()

        resp = self.client.get(
            "/api/v1/integrations/drive/status/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_connected"])
        self.assertEqual(data["google_email"], "user@gmail.com")

    def test_drive_status_requires_auth(self):
        resp = self.client.get("/api/v1/integrations/drive/status/")
        self.assertEqual(resp.status_code, 401)

    def test_drive_disconnect_not_connected(self):
        resp = self.client.delete(
            "/api/v1/integrations/drive/disconnect/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(resp.status_code, 404)

    def test_drive_disconnect_removes_token(self):
        t = GoogleDriveToken.objects.create(user=self.user, google_email="x@gmail.com")
        t.set_credentials({"token": "x", "refresh_token": "y"})
        t.save()

        resp = self.client.delete(
            "/api/v1/integrations/drive/disconnect/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(GoogleDriveToken.objects.filter(user=self.user).exists())


class DriveConnectAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="connectuser",
            email="connect@test.com",
            password="testpass123",
        )
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)

    def test_drive_connect_returns_url(self):
        # Patch module-level credentials in google_drive (the view imports them
        # from there via `from .google_drive import GOOGLE_CLIENT_ID, ...`) and
        # stub the URL builder so the test never contacts Google's servers.
        with (
            patch("apps.integrations.google_drive.GOOGLE_CLIENT_ID", "fake-client-id"),
            patch("apps.integrations.google_drive.GOOGLE_CLIENT_SECRET", "fake-secret"),
            patch(
                "apps.integrations.google_drive.get_oauth2_authorization_url",
                return_value="https://accounts.google.com/o/oauth2/auth?fake=1",
            ),
        ):
            resp = self.client.get(
                "/api/v1/integrations/drive/connect/",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("authorization_url", resp.json())


class S3ServiceTest(TestCase):
    @patch("apps.integrations.s3.boto3.client")
    def test_get_presigned_url(self, mock_boto):
        """get_presigned_url should call generate_presigned_url on boto3 client."""
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.presigned.url/file"
        mock_boto.return_value = mock_s3

        url = get_presigned_url("my-bucket", "documents/test.pdf", expiry_seconds=3600)
        self.assertEqual(url, "https://s3.presigned.url/file")
        mock_s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "my-bucket", "Key": "documents/test.pdf"},
            ExpiresIn=3600,
        )

    @patch("apps.integrations.s3.boto3.client")
    def test_upload_to_s3_missing_file(self, mock_boto):
        """upload_to_s3 should raise FileNotFoundError for missing file."""
        with self.assertRaises(FileNotFoundError):
            upload_to_s3("/nonexistent/path/file.pdf", bucket="test-bucket")
