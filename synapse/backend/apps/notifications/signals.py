"""
Signals for the Notifications app.

Pushes new Notification records to the user's WebSocket channel in real-time
via Django Channels so the frontend badge updates instantly without polling.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="notifications.Notification")
def push_notification_on_create(sender, instance, created, **kwargs):
    """
    When a Notification is created, push it immediately to the user's
    WebSocket channel group (notifications_{user_id}).

    This is non-blocking — failures are logged but never raise.
    """
    if not created:
        return  # Only push on create, not on updates (mark-read etc.)

    try:
        from apps.notifications.tasks import push_notification_to_ws

        push_notification_to_ws(instance)
    except Exception as exc:
        logger.warning("Failed to push notification %s via WS: %s", instance.id, exc)
