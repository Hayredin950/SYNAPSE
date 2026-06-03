"""
backend.apps.users.tests.test_me_view
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for the GET/PATCH /api/v1/auth/me/ endpoint.

Covers:
  - Returns 401 when unauthenticated
  - Returns user fields when authenticated
  - Returns bio, role, avatar_url, preferences
  - PATCH updates first_name, last_name, bio
  - PATCH returns {success, data} response shape
  - Read-only fields (id, email, role) cannot be changed
"""

from __future__ import annotations

import uuid

from apps.users.models import User

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


def _make_user() -> User:
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        username=f"me_test_{uid}",
        email=f"me_test_{uid}@example.com",
        password="pass12345",
        first_name="Test",
        last_name="User",
    )


class MeViewGetTests(TestCase):
    """GET /api/v1/auth/me/"""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user()
        self.url = "/api/v1/auth/me/"

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertIn(
            resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )

    def test_authenticated_returns_200(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_returns_username(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.data["username"], self.user.username)

    def test_returns_email(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.data["email"], self.user.email)

    def test_returns_expected_fields(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        for field in (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "bio",
            "role",
            "created_at",
        ):
            self.assertIn(field, resp.data, f"Missing field: {field}")

    def test_does_not_return_password(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertNotIn("password", resp.data)


class MeViewPatchTests(TestCase):
    """PATCH /api/v1/auth/me/"""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user()
        self.url = "/api/v1/auth/me/"
        self.client.force_authenticate(user=self.user)

    def test_patch_first_name(self):
        resp = self.client.patch(self.url, {"first_name": "Updated"}, format="json")
        self.assertIn(resp.status_code, [status.HTTP_200_OK])
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")

    def test_patch_bio(self):
        resp = self.client.patch(
            self.url, {"bio": "AI engineer @ SYNAPSE"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, "AI engineer @ SYNAPSE")

    def test_patch_returns_success_true(self):
        resp = self.client.patch(self.url, {"first_name": "X"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("success"))

    def test_patch_returns_data_with_updated_values(self):
        resp = self.client.patch(self.url, {"first_name": "NewName"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["first_name"], "NewName")

    def test_read_only_email_not_changed(self):
        original_email = self.user.email
        self.client.patch(self.url, {"email": "hacker@evil.com"}, format="json")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)

    def test_read_only_role_not_changed(self):
        original_role = self.user.role
        self.client.patch(self.url, {"role": "admin"}, format="json")
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, original_role)

    def test_unauthenticated_patch_returns_401(self):
        client = APIClient()
        resp = client.patch(self.url, {"first_name": "Hacker"}, format="json")
        self.assertIn(
            resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )
