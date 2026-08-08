import pytest
from apps.users.models import User

from django.test import TestCase


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="SecurePass123!"
        )
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.role, User.Role.USER)
        self.assertTrue(user.check_password("SecurePass123!"))

    def test_user_str(self):
        user = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="SecurePass123!"
        )
        self.assertEqual(str(user), "test2@example.com")

    def test_is_premium_false_for_regular_user(self):
        user = User.objects.create_user(
            username="regular", email="regular@example.com", password="SecurePass123!"
        )
        self.assertFalse(user.is_premium)

    def test_is_premium_true_for_premium_user(self):
        user = User.objects.create_user(
            username="premium",
            email="premium@example.com",
            password="SecurePass123!",
        )
        user.role = User.Role.PREMIUM
        user.save()
        self.assertTrue(user.is_premium)

    def test_uuid_primary_key(self):
        user = User.objects.create_user(
            username="uuidtest", email="uuid@example.com", password="SecurePass123!"
        )
        import uuid

        self.assertIsInstance(user.id, uuid.UUID)
