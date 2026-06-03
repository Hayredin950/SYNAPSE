"""
Views for the Notifications app.

Endpoints:
  GET  /api/v1/notifications/              — list user notifications
  GET  /api/v1/notifications/unread-count/ — count of unread notifications
  POST /api/v1/notifications/<id>/read/    — mark single notification as read
  POST /api/v1/notifications/read-all/     — mark all notifications as read
  DELETE /api/v1/notifications/<id>/       — delete a notification
"""

import logging

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)


class NotificationListView(generics.ListAPIView):
    """
    GET /api/v1/notifications/
    List the current user's notifications (most recent first).
    Supports ?is_read=true/false filtering.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() == "true")
        return qs


class NotificationUnreadCountView(APIView):
    """
    GET /api/v1/notifications/unread-count/
    Returns the count of unread notifications for the authenticated user.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})


class NotificationMarkReadView(APIView):
    """
    POST /api/v1/notifications/<id>/read/
    Mark a single notification as read.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response(
                {"detail": "Notification not found."}, status=status.HTTP_404_NOT_FOUND
            )
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(
            {"detail": "Notification marked as read."}, status=status.HTTP_200_OK
        )


class NotificationMarkAllReadView(APIView):
    """
    POST /api/v1/notifications/read-all/
    Mark all of the current user's notifications as read.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True
        )
        logger.info(
            f"Marked {updated} notifications as read for user {request.user.email}"
        )
        return Response(
            {"detail": f"{updated} notifications marked as read."},
            status=status.HTTP_200_OK,
        )


class NotificationDeleteView(generics.DestroyAPIView):
    """
    DELETE /api/v1/notifications/<id>/
    Delete a specific notification.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
