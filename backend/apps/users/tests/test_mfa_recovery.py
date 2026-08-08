"""
TASK-002-T1 — Unit tests for MFA backup code generation, hashing, verification.
TASK-002-T3 — Integration tests for recovery code login via /mfa/verify-backup/.
"""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, PropertyMock, patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_user(email="mfa@test.com", password="TestPass123!"):
    """Create a real User for integration tests."""
    import uuid

    from django.contrib.auth import get_user_model

    User = get_user_model()
    username = email.split("@")[0] + "_" + str(uuid.uuid4())[:8]
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name="MFA",
        last_name="Test",
    )
    # Ensure preferences dict exists
    if not hasattr(user, "preferences") or user.preferences is None:
        user.preferences = {}
        user.save(update_fields=["preferences"])
    return user


# ── TASK-002-T1: Unit tests for backup code generation + hashing ──────────────


class TestBackupCodeGeneration(TestCase):

    def setUp(self):
        self.user = _make_user()

    def test_generate_backup_codes_returns_10(self):
        from apps.users.mfa import _generate_backup_codes

        codes = _generate_backup_codes(self.user)
        self.assertEqual(len(codes), 10)

    def test_backup_codes_format(self):
        """Codes should be XXXX-XXXX-XXXX format."""
        from apps.users.mfa import _generate_backup_codes

        codes = _generate_backup_codes(self.user)
        for code in codes:
            parts = code.split("-")
            self.assertEqual(len(parts), 3, f"Expected 3 parts in {code}")
            self.assertTrue(
                all(len(p) == 4 for p in parts), f"Each part should be 4 chars: {code}"
            )

    def test_backup_codes_stored_as_hashes(self):
        """Plain-text codes should NOT appear in user.preferences."""
        from apps.users.mfa import _generate_backup_codes

        codes = _generate_backup_codes(self.user)
        stored = self.user.preferences.get("mfa_backup_codes", [])
        self.assertEqual(len(stored), 10)
        # Verify none of the plain codes appear in the stored list
        for code in codes:
            self.assertNotIn(code, stored)

    def test_backup_codes_hashed_with_sha256(self):
        """Each stored hash should be the SHA-256 of the corresponding plain code."""
        from apps.users.mfa import _generate_backup_codes

        codes = _generate_backup_codes(self.user)
        stored = self.user.preferences.get("mfa_backup_codes", [])
        for code, hashed in zip(codes, stored):
            expected = hashlib.sha256(code.encode()).hexdigest()
            self.assertEqual(expected, hashed)

    def test_backup_codes_are_unique(self):
        """All 10 backup codes should be unique."""
        from apps.users.mfa import _generate_backup_codes

        codes = _generate_backup_codes(self.user)
        self.assertEqual(len(set(codes)), 10)

    def test_regenerate_replaces_old_codes(self):
        """Calling _generate_backup_codes twice should replace the old codes."""
        from apps.users.mfa import _generate_backup_codes

        codes1 = _generate_backup_codes(self.user)
        codes2 = _generate_backup_codes(self.user)
        self.assertNotEqual(set(codes1), set(codes2))
        stored = self.user.preferences.get("mfa_backup_codes", [])
        self.assertEqual(len(stored), 10)


class TestVerifyBackupCode(TestCase):

    def setUp(self):
        self.user = _make_user(email="backup@test.com")
        from apps.users.mfa import _generate_backup_codes

        self.plain_codes = _generate_backup_codes(self.user)

    def test_valid_code_returns_true(self):
        from apps.users.mfa import verify_backup_code

        result = verify_backup_code(self.user, self.plain_codes[0])
        self.assertTrue(result)

    def test_valid_code_is_consumed(self):
        """After use, the same code should not work again (single-use)."""
        from apps.users.mfa import verify_backup_code

        verify_backup_code(self.user, self.plain_codes[0])
        # Reload from DB
        self.user.refresh_from_db()
        result = verify_backup_code(self.user, self.plain_codes[0])
        self.assertFalse(result)

    def test_remaining_count_decreases(self):
        from apps.users.mfa import verify_backup_code

        initial = len(self.user.preferences.get("mfa_backup_codes", []))
        verify_backup_code(self.user, self.plain_codes[0])
        self.user.refresh_from_db()
        remaining = len(self.user.preferences.get("mfa_backup_codes", []))
        self.assertEqual(remaining, initial - 1)

    def test_invalid_code_returns_false(self):
        from apps.users.mfa import verify_backup_code

        result = verify_backup_code(self.user, "XXXX-XXXX-XXXX")
        self.assertFalse(result)

    def test_wrong_format_returns_false(self):
        from apps.users.mfa import verify_backup_code

        result = verify_backup_code(self.user, "not-a-valid-code")
        self.assertFalse(result)

    def test_empty_code_returns_false(self):
        from apps.users.mfa import verify_backup_code

        result = verify_backup_code(self.user, "")
        self.assertFalse(result)

    def test_code_case_insensitive(self):
        """Codes should work regardless of case."""
        from apps.users.mfa import verify_backup_code

        code = self.plain_codes[1]
        result = verify_backup_code(self.user, code.lower())
        self.assertTrue(result)

    def test_all_10_codes_valid(self):
        """All 10 generated codes should be valid."""
        from apps.users.mfa import _generate_backup_codes, verify_backup_code

        # Regenerate fresh set
        user2 = _make_user(email="all10@test.com")
        codes = _generate_backup_codes(user2)
        for code in codes:
            user2.refresh_from_db()
            self.assertTrue(verify_backup_code(user2, code))


# ── TASK-002-T3: Integration tests — /mfa/verify-backup/ endpoint ─────────────


class TestVerifyBackupEndpoint(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user(email="endpoint@test.com")
        from apps.users.mfa import _generate_backup_codes

        self.codes = _generate_backup_codes(self.user)
        self.client.force_authenticate(user=self.user)

    def test_valid_backup_code_returns_200_with_tokens(self):
        resp = self.client.post(
            "/api/v1/auth/mfa/verify-backup/",
            {"code": self.codes[0]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_invalid_backup_code_returns_401(self):
        resp = self.client.post(
            "/api/v1/auth/mfa/verify-backup/",
            {"code": "XXXX-XXXX-XXXX"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(resp.data["success"])

    def test_already_used_code_returns_401(self):
        """Using the same backup code twice should fail on second attempt."""
        self.client.post(
            "/api/v1/auth/mfa/verify-backup/",
            {"code": self.codes[0]},
            format="json",
        )
        self.user.refresh_from_db()
        resp = self.client.post(
            "/api/v1/auth/mfa/verify-backup/",
            {"code": self.codes[0]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_code_returns_400(self):
        resp = self.client.post(
            "/api/v1/auth/mfa/verify-backup/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            "/api/v1/auth/mfa/verify-backup/",
            {"code": self.codes[0]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
