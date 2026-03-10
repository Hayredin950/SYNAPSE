from apps.users.models import User

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@override_settings(AXES_ENABLED=False)
class AuthEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse("auth-register")
        self.login_url = reverse("auth-login")
        self.me_url = reverse("auth-me")

    def test_register_success(self):
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "SecurePass123!",
            "password2": "SecurePass123!",
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        # Registration now requires email verification — no tokens issued yet.
        self.assertIn("user", response.data)
        self.assertFalse(response.data["user"]["email_verified"])
        self.assertNotIn("tokens", response.data)

    def test_register_duplicate_email(self):
        User.objects.create_user(
            username="existing", email="dup@example.com", password="Pass123!"
        )
        data = {
            "username": "newuser2",
            "email": "dup@example.com",
            "password": "SecurePass123!",
            "password2": "SecurePass123!",
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_mismatch(self):
        data = {
            "username": "mismatch",
            "email": "mismatch@example.com",
            "password": "SecurePass123!",
            "password2": "WrongPass456!",
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_success(self):
        User.objects.create_user(
            username="loginuser", email="login@example.com", password="SecurePass123!"
        )
        response = self.client.post(
            self.login_url, {"email": "login@example.com", "password": "SecurePass123!"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_wrong_password(self):
        User.objects.create_user(
            username="loginuser2", email="login2@example.com", password="SecurePass123!"
        )
        response = self.client.post(
            self.login_url, {"email": "login2@example.com", "password": "WrongPass!"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_auth(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_profile(self):
        user = User.objects.create_user(
            username="meuser", email="me@example.com", password="SecurePass123!"
        )
        self.client.force_authenticate(user=user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "me@example.com")
