"""
Integration tests for Notification API views.
"""

from apps.notifications.models import Notification
from apps.users.models import User

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class NotificationAPITestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

        # Create notifications for the test user
        self.notif1 = Notification.objects.create(
            user=self.user,
            title="Notification 1",
            message="Message 1",
            notif_type="info",
            is_read=False,
        )
        self.notif2 = Notification.objects.create(
            user=self.user,
            title="Notification 2",
            message="Message 2",
            notif_type="workflow_complete",
            is_read=True,
        )
        # Notification for other user — should not be visible
        Notification.objects.create(
            user=self.other_user,
            title="Other User Notif",
            message="Not yours",
        )

    # ── List ──────────────────────────────────────────────────────────────────

    def _get_results(self, data):
        """Handle wrapped, paginated, and plain list API responses."""
        if isinstance(data, dict):
            # Custom wrapper: {'success': True, 'data': [...], 'meta': {...}}
            if "data" in data:
                return list(data["data"])
            # Standard DRF pagination: {'count': N, 'results': [...]}
            if "results" in data:
                return list(data["results"])
        if isinstance(data, list):
            return data
        return list(data)

    def test_list_notifications(self):
        url = reverse("notification-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response.data)
        titles = [n["title"] for n in results]
        self.assertIn("Notification 1", titles)
        self.assertIn("Notification 2", titles)
        self.assertNotIn("Other User Notif", titles)

    def test_filter_unread_notifications(self):
        url = reverse("notification-list") + "?is_read=false"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response.data)
        for n in results:
            self.assertFalse(n["is_read"])

    def test_filter_read_notifications(self):
        url = reverse("notification-list") + "?is_read=true"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response.data)
        for n in results:
            self.assertTrue(n["is_read"])

    def test_unauthenticated_access_denied(self):
        self.client.force_authenticate(user=None)
        url = reverse("notification-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Unread Count ──────────────────────────────────────────────────────────

    def test_unread_count(self):
        url = reverse("notification-unread-count")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unread_count"], 1)

    # ── Mark Read ─────────────────────────────────────────────────────────────

    def test_mark_single_notification_read(self):
        url = reverse("notification-mark-read", kwargs={"pk": self.notif1.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.notif1.refresh_from_db()
        self.assertTrue(self.notif1.is_read)

    def test_mark_read_other_user_notification_404(self):
        other_notif = Notification.objects.create(
            user=self.other_user,
            title="Other",
            message="Not yours",
        )
        url = reverse("notification-mark-read", kwargs={"pk": other_notif.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_all_read(self):
        url = reverse("notification-read-all")
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        unread_count = Notification.objects.filter(
            user=self.user, is_read=False
        ).count()
        self.assertEqual(unread_count, 0)

    # ── Delete ────────────────────────────────────────────────────────────────

    def test_delete_notification(self):
        url = reverse("notification-delete", kwargs={"pk": self.notif1.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(id=self.notif1.id).exists())

    def test_delete_other_user_notification_404(self):
        other_notif = Notification.objects.create(
            user=self.other_user,
            title="Other",
            message="Not yours",
        )
        url = reverse("notification-delete", kwargs={"pk": other_notif.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
