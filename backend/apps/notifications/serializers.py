"""
Serializers for the Notifications app.
"""

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""

    # Frontend expects `type` (not `notif_type`) and `read` (not `is_read`)
    type = serializers.CharField(source="notif_type", read_only=True)
    read = serializers.BooleanField(source="is_read", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "notif_type",
            "type",
            "is_read",
            "read",
            "created_at",
            "metadata",
        ]
        read_only_fields = [
            "id",
            "title",
            "message",
            "notif_type",
            "type",
            "created_at",
            "metadata",
            "read",
        ]
