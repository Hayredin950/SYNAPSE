"""
backend.apps.integrations.models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Models for storing cloud integration tokens & connection state.

Phase 6.1 — Google Drive Integration (Week 17)
Phase 6.2 — AWS S3 Integration  (Week 18)
"""

from __future__ import annotations

import base64
import hashlib
import uuid

from cryptography.fernet import Fernet

from django.conf import settings
from django.db import models


def _fernet():
    """Return a Fernet instance derived from Django's SECRET_KEY."""
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class GoogleDriveToken(models.Model):
    """
    Stores an encrypted OAuth2 token for a user's connected Google Drive account.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_drive_token",
    )
    # Encrypted JSON blob: {access_token, refresh_token, token_uri, client_id, client_secret, scopes}
    encrypted_credentials = models.TextField()
    google_email = models.EmailField(blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "google_drive_tokens"
        verbose_name = "Google Drive Token"

    def __str__(self):
        return f"DriveToken({self.user_id})"

    # ── encryption helpers ─────────────────────────────────────────────────

    def set_credentials(self, credentials_dict: dict) -> None:
        """Encrypt and store credentials dict."""
        import json

        raw = json.dumps(credentials_dict).encode()
        self.encrypted_credentials = _fernet().encrypt(raw).decode()

    def get_credentials(self) -> dict:
        """Decrypt and return credentials dict."""
        import json

        raw = _fernet().decrypt(self.encrypted_credentials.encode())
        return json.loads(raw)

    @property
    def is_connected(self) -> bool:
        return bool(self.encrypted_credentials)
