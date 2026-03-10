"""
TASK-605-B2: API Key Authentication for DRF.

Reads Authorization: Bearer sk-syn-{key} header,
hashes it, looks up the APIKey, updates last_used,
and returns (user, api_key) as the authenticated credentials.

Applied globally alongside JWT session auth via DEFAULT_AUTHENTICATION_CLASSES.
"""

from __future__ import annotations

import hashlib
import logging

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

logger = logging.getLogger(__name__)

API_KEY_PREFIX = "sk-syn-"


class APIKeyAuthentication(BaseAuthentication):
    """
    Authenticate via API key in the Authorization header.

    Header format:
        Authorization: Bearer sk-syn-<random chars>

    On success: returns (user, api_key_instance)
    On failure: raises AuthenticationFailed or returns None (to try next authenticator)
    """

    def authenticate(self, request: Request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None  # Let other authenticators handle it

        raw_token = auth_header[7:].strip()  # strip "Bearer "

        if not raw_token.startswith(API_KEY_PREFIX):
            return None  # Not an API key — let JWT auth handle it

        return self._authenticate_key(raw_token)

    def _authenticate_key(self, raw_key: str):
        from apps.users.models import APIKey

        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        try:
            api_key = APIKey.objects.select_related("user").get(
                key_hash=key_hash, is_active=True
            )
        except APIKey.DoesNotExist:
            raise AuthenticationFailed("Invalid or revoked API key.")

        if api_key.expires_at and api_key.expires_at < timezone.now():
            raise AuthenticationFailed("API key has expired.")

        # Update last_used (non-blocking UPDATE — no race conditions)
        APIKey.objects.filter(pk=api_key.pk).update(last_used=timezone.now())

        logger.debug(
            "API key auth: user=%s key=%s", api_key.user_id, api_key.key_prefix
        )
        return (api_key.user, api_key)

    def authenticate_header(self, request: Request) -> str:
        return 'Bearer realm="synapse-api-key"'
