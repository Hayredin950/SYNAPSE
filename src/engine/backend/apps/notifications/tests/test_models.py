"""
Unit tests for Notification model.
"""

import uuid

from apps.notifications.models import Notification
from apps.users.models import User

from django.test import TestCase


class NotificationModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.notification = Notification.objects.create(
            user=self.user,
            title="Test Notification",
            message="This is a test notification.",
            notif_type="info",
        )

    def test_notification_str(self):
        self.assertIn("Test Notification", str(self.notification))
        self.assertIn(self.user.email, str(self.notification))

    def test_notification_defaults(self):
        self.assertFalse(self.notification.is_read)
        self.assertEqual(self.notification.notif_type, "info")
        self.assertEqual(self.notification.metadata, {})

    def test_notification_uuid_pk(self):
        self.assertIsInstance(self.notification.id, uuid.UUID)

    def test_notification_ordering(self):
        n2 = Notification.objects.create(
            user=self.user,
            title="Second",
            message="Second notification",
        )
        notifications = list(Notification.objects.filter(user=self.user))
        self.assertEqual(notifications[0].id, n2.id)  # newest first

    def test_notification_metadata_json(self):
        n = Notification.objects.create(
            user=self.user,
            title="With Meta",
            message="Has metadata",
            metadata={"workflow_id": "abc-123", "run_count": 5},
        )
        self.assertEqual(n.metadata["workflow_id"], "abc-123")
        self.assertEqual(n.metadata["run_count"], 5)

    def test_notification_cascade_delete(self):
        user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="pass",
        )
        Notification.objects.create(
            user=user2,
            title="Will be deleted",
            message="When user deleted",
        )
        user2_id = user2.id
        user2.delete()
        self.assertEqual(Notification.objects.filter(user_id=user2_id).count(), 0)
