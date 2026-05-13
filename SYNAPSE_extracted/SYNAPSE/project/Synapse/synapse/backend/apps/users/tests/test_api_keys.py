"""
TASK-605 — API Key management tests.

B1: APIKey model (create_key, authenticate, prefix stored, hash not raw)
B4: Management endpoints (list, create, revoke)
"""

import hashlib

import pytest
from apps.users.models import APIKey, User
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework import status
from rest_framework.test import APIClient


def make_user(username, email):
    return User.objects.create_user(
        username=username, email=email, password="testpass123"
    )


def auth_client(user):
    c = APIClient()
    token = RefreshToken.for_user(user)
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return c


@pytest.fixture
def user(db):
    return make_user("devuser", "dev@example.com")


@pytest.fixture
def client_auth(user):
    return auth_client(user)


@pytest.mark.django_db
class TestAPIKeyModel:
    def test_create_key_returns_raw_key(self, user):
        key, raw = APIKey.create_key(user, name="Test Key")
        assert raw.startswith("sk-syn-")
        assert len(raw) > 15

    def test_key_hash_stored_not_raw(self, user):
        key, raw = APIKey.create_key(user, name="Hashed")
        expected_hash = hashlib.sha256(raw.encode()).hexdigest()
        assert key.key_hash == expected_hash
        assert raw not in key.key_hash  # raw key NOT stored

    def test_key_prefix_matches_raw(self, user):
        key, raw = APIKey.create_key(user, name="Prefix")
        assert key.key_prefix == raw[:12]

    def test_authenticate_success(self, user):
        key, raw = APIKey.create_key(user, name="Auth test")
        found = APIKey.authenticate(raw)
        assert found is not None
        assert found.pk == key.pk

    def test_authenticate_wrong_key_returns_none(self, user):
        APIKey.create_key(user, name="Wrong")
        assert APIKey.authenticate("sk-syn-wrongkey") is None

    def test_authenticate_revoked_returns_none(self, user):
        key, raw = APIKey.create_key(user, name="Revoked")
        key.is_active = False
        key.save()
        assert APIKey.authenticate(raw) is None

    def test_str(self, user):
        key, _ = APIKey.create_key(user, name="My Key")
        assert "My Key" in str(key)


@pytest.mark.django_db
class TestAPIKeyListCreate:
    URL = "/api/v1/users/keys/"

    def test_unauthenticated_401(self):
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_empty(self, client_auth):
        resp = client_auth.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"] == []

    def test_create_key_returns_full_key_once(self, client_auth):
        resp = client_auth.post(
            self.URL, {"name": "My Dev Key", "scopes": ["read:content"]}, format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.data["data"]
        assert data["key"].startswith("sk-syn-")
        assert "warning" in resp.data

    def test_create_key_appears_in_list(self, client_auth):
        client_auth.post(self.URL, {"name": "Listed Key"}, format="json")
        resp = client_auth.get(self.URL)
        assert len(resp.data["data"]) == 1
        # Full key NOT in list response
        assert "key" not in resp.data["data"][0]

    def test_create_requires_name(self, client_auth):
        resp = client_auth.post(self.URL, {"name": ""}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_max_10_keys(self, client_auth, user):
        for i in range(10):
            APIKey.create_key(user, name=f"Key {i}")
        resp = client_auth.post(self.URL, {"name": "Key 11"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAPIKeyRevoke:
    def test_revoke_key(self, client_auth, user):
        key, raw = APIKey.create_key(user, name="To Revoke")
        resp = client_auth.delete(f"/api/v1/users/keys/{key.id}/")
        assert resp.status_code == status.HTTP_200_OK
        key.refresh_from_db()
        assert key.is_active is False

    def test_cannot_revoke_others_key(self, db, user):
        other = make_user("other2", "other2@example.com")
        key, _ = APIKey.create_key(other, name="Not mine")
        c = auth_client(user)
        resp = c.delete(f"/api/v1/users/keys/{key.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_revoke_nonexistent_404(self, client_auth):
        import uuid

        resp = client_auth.delete(f"/api/v1/users/keys/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
