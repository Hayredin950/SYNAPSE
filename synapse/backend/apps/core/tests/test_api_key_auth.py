"""
TASK-605-B2: APIKeyAuthentication tests.

Covers:
  - Valid API key → authenticated user
  - Invalid/revoked/expired key → 401
  - Non-key Bearer token → falls through to JWT auth (returns None)
  - Missing Authorization header → None (falls through)
  - last_used timestamp updated on successful auth
"""

import hashlib
from datetime import timedelta
from unittest.mock import patch

import pytest
from apps.core.auth import APIKeyAuthentication
from apps.users.models import APIKey, User

from django.utils import timezone
from rest_framework.test import APIRequestFactory

# ── helpers ───────────────────────────────────────────────────────────────────


def make_user():
    import uuid as _u

    h = _u.uuid4().hex[:8]
    return User.objects.create_user(
        username=f"devuser_{h}", email=f"{h}@test.com", password="pass"
    )


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAPIKeyAuthentication:
    """Unit tests — call authenticate() directly."""

    def _make_request(self, auth_header: str | None = None):
        factory = APIRequestFactory()
        req = factory.get("/api/v1/content/articles/")
        if auth_header:
            req.META["HTTP_AUTHORIZATION"] = auth_header
        return req

    def test_no_header_returns_none(self):
        auth = APIKeyAuthentication()
        req = self._make_request()
        assert auth.authenticate(req) is None

    def test_non_bearer_returns_none(self):
        auth = APIKeyAuthentication()
        req = self._make_request("Token sometoken")
        assert auth.authenticate(req) is None

    def test_jwt_bearer_returns_none(self, db):
        """Bearer that doesn't start with sk-syn- → None (let JWT handle it)."""
        auth = APIKeyAuthentication()
        req = self._make_request("Bearer eyJhbGciOiJIUzI1NiJ9.dummy")
        assert auth.authenticate(req) is None

    def test_valid_key_returns_user_and_key(self, db):
        user = make_user()
        key, raw = APIKey.create_key(user, name="Test")
        auth = APIKeyAuthentication()
        req = self._make_request(f"Bearer {raw}")
        result = auth.authenticate(req)
        assert result is not None
        returned_user, returned_key = result
        assert returned_user.pk == user.pk
        assert returned_key.pk == key.pk

    def test_invalid_key_raises_401(self, db):
        from rest_framework.exceptions import AuthenticationFailed

        auth = APIKeyAuthentication()
        req = self._make_request("Bearer sk-syn-thisisnotavalidkey12345678")
        with pytest.raises(AuthenticationFailed):
            auth.authenticate(req)

    def test_revoked_key_raises_401(self, db):
        from rest_framework.exceptions import AuthenticationFailed

        user = make_user()
        key, raw = APIKey.create_key(user, name="Revoked")
        key.is_active = False
        key.save()
        auth = APIKeyAuthentication()
        req = self._make_request(f"Bearer {raw}")
        with pytest.raises(AuthenticationFailed):
            auth.authenticate(req)

    def test_expired_key_raises_401(self, db):
        from rest_framework.exceptions import AuthenticationFailed

        user = make_user()
        key, raw = APIKey.create_key(user, name="Expired")
        key.expires_at = timezone.now() - timedelta(hours=1)
        key.save()
        auth = APIKeyAuthentication()
        req = self._make_request(f"Bearer {raw}")
        with pytest.raises(AuthenticationFailed):
            auth.authenticate(req)

    def test_last_used_updated(self, db):
        user = make_user()
        key, raw = APIKey.create_key(user, name="LastUsed")
        assert key.last_used is None
        auth = APIKeyAuthentication()
        req = self._make_request(f"Bearer {raw}")
        auth.authenticate(req)
        key.refresh_from_db()
        assert key.last_used is not None

    def test_authenticate_header_returns_realm(self):
        auth = APIKeyAuthentication()
        req = self._make_request()
        assert "synapse-api-key" in auth.authenticate_header(req)


@pytest.mark.django_db
class TestPublicAPIEndpoints:
    """Integration tests for the public API endpoints."""

    def _auth_header(self, user):
        key, raw = APIKey.create_key(user, name="Test")
        return {"HTTP_AUTHORIZATION": f"Bearer {raw}"}

    def test_articles_requires_auth(self):
        from rest_framework.test import APIClient

        resp = APIClient().get("/api/v1/content/articles/")
        assert resp.status_code == 401

    def test_articles_with_api_key(self, db):
        from rest_framework.test import APIClient

        user = make_user()
        c = APIClient()
        key, raw = APIKey.create_key(user, name="ArticlesKey")
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        resp = c.get("/api/v1/content/articles/")
        assert resp.status_code == 200
        assert "data" in resp.data

    def test_papers_with_api_key(self, db):
        from rest_framework.test import APIClient

        user = make_user()
        c = APIClient()
        key, raw = APIKey.create_key(user, name="PapersKey")
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        resp = c.get("/api/v1/content/papers/")
        assert resp.status_code == 200

    def test_repos_with_api_key(self, db):
        from rest_framework.test import APIClient

        user = make_user()
        c = APIClient()
        key, raw = APIKey.create_key(user, name="ReposKey")
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        resp = c.get("/api/v1/content/repos/")
        assert resp.status_code == 200

    def test_trends_with_api_key(self, db):
        from rest_framework.test import APIClient

        user = make_user()
        c = APIClient()
        key, raw = APIKey.create_key(user, name="TrendsKey")
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        resp = c.get("/api/v1/trends/")
        assert resp.status_code == 200

    def test_ai_query_requires_question(self, db):
        from rest_framework.test import APIClient

        user = make_user()
        c = APIClient()
        key, raw = APIKey.create_key(user, name="AIKey")
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        resp = c.post("/api/v1/ai/query/", {}, format="json")
        assert resp.status_code == 400
        assert "question" in str(resp.data)
