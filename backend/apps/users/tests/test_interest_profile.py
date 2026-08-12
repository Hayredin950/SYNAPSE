"""
backend.apps.users.tests.test_interest_profile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for the GET/PUT /api/v1/users/me/interests/ endpoint.

Covers:
  - Returns 401 when unauthenticated
  - PUT requires a non-empty topics list
  - PUT stores the profile in user.preferences["interest_profile"]
  - PUT mirrors topics into OnboardingPreferences.interests (normalized slugs)
  - GET returns the saved profile
  - PUT does not clobber other preferences (e.g. API keys)
"""

from __future__ import annotations

import uuid

from apps.users.models import OnboardingPreferences, User

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


def _make_user() -> User:
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        username=f"int_test_{uid}",
        email=f"int_test_{uid}@example.com",
        password="pass12345",
    )


class InterestProfileTests(TestCase):
    """GET/PUT /api/v1/users/me/interests/"""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user()

    def test_unauthenticated_returns_401(self):
        resp = self.client.put(
            "/api/v1/users/me/interests/", {"topics": ["ai"]}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_topics_rejected(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(
            "/api/v1/users/me/interests/", {"topics": []}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_stores_profile(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(
            "/api/v1/users/me/interests/",
            {"topics": ["ai", "web"], "experience": "mid", "goals": ["learn"]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        profile = self.user.preferences["interest_profile"]
        self.assertEqual(profile["topics"], ["ai", "web"])
        self.assertEqual(profile["experience"], "mid")
        self.assertEqual(profile["goals"], ["learn"])

    def test_put_mirrors_topics_to_onboarding_slugs(self):
        self.client.force_authenticate(user=self.user)
        self.client.put(
            "/api/v1/users/me/interests/",
            {"topics": ["ai", "web", "rust"]},
            format="json",
        )
        prefs = OnboardingPreferences.objects.get(user=self.user)
        self.assertIn("ai_ml", prefs.interests)  # "ai" → ai_ml
        self.assertIn("web_dev", prefs.interests)  # "web" → web_dev
        self.assertIn("programming", prefs.interests)  # "rust" → programming

    def test_put_merges_with_existing_interests(self):
        self.client.force_authenticate(user=self.user)
        prefs, _ = OnboardingPreferences.objects.get_or_create(user=self.user)
        prefs.interests = ["ai_ml"]
        prefs.save()
        self.client.put(
            "/api/v1/users/me/interests/", {"topics": ["web"]}, format="json"
        )
        prefs.refresh_from_db()
        self.assertEqual(prefs.interests, ["ai_ml", "web_dev"])

    def test_put_does_not_clobber_api_keys(self):
        self.user.preferences = {"gemini_api_key": "secret-key-value-123"}
        self.user.save(update_fields=["preferences"])
        self.client.force_authenticate(user=self.user)
        self.client.put(
            "/api/v1/users/me/interests/", {"topics": ["ai"]}, format="json"
        )
        self.user.refresh_from_db()
        self.assertEqual(
            self.user.preferences["gemini_api_key"], "secret-key-value-123"
        )
        self.assertIn("interest_profile", self.user.preferences)

    def test_get_returns_profile(self):
        self.user.preferences = {"interest_profile": {"topics": ["ai"]}}
        self.user.save(update_fields=["preferences"])
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/v1/users/me/interests/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["topics"], ["ai"])

    def test_get_empty_profile(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/v1/users/me/interests/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"], {})
