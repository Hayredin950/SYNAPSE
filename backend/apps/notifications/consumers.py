"""
Notification WebSocket Consumer
================================
Authenticated users connect to ws://host/ws/notifications/
and receive real-time notification events pushed from Celery tasks
via the Django Channels layer (Redis backend).

Usage from server-side (e.g. tasks.py):
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"notifications_{user_id}",
        {
            "type": "notify",
            "data": {
                "id": str(notification.id),
                "title": notification.title,
                "message": notification.message,
                "notif_type": notification.notif_type,
                "is_read": False,
                "created_at": notification.created_at.isoformat(),
                "metadata": notification.metadata or {},
            }
        }
    )
"""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Per-user WebSocket channel.
    Group name: notifications_<user_id>
    """

    async def connect(self):
        # Accept the connection first; auth happens via first message (token frame)
        # OR via Django session/scope user if already authenticated via middleware.
        user = self.scope.get("user")
        if user and user.is_authenticated:
            # Already authenticated via session middleware
            self.user_id = str(user.id)
            self.group_name = f"notifications_{self.user_id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(
                "WS connected (session): user=%s group=%s",
                self.user_id,
                self.group_name,
            )
        else:
            # Accept temporarily — wait for auth message with token
            await self.accept()
            self.user_id = None
            self.group_name = None
            self._authenticated = False

    async def disconnect(self, close_code):
        # Important: connect() sets self.group_name = None for unauthenticated
        # sockets, so `hasattr` is not enough — the attribute exists but is None.
        # Channels' group_discard() requires a real string, otherwise it raises
        # `TypeError: Group name must be a valid unicode string with length < 100`
        # (the error Sentry surfaced).
        group_name = getattr(self, "group_name", None)
        if group_name and isinstance(group_name, str):
            try:
                await self.channel_layer.group_discard(group_name, self.channel_name)
            except Exception as exc:
                logger.warning("WS group_discard failed (non-critical): %s", exc)
        logger.info(
            "WS disconnected: user=%s code=%s",
            getattr(self, "user_id", "?"),
            close_code,
        )

    async def receive(self, text_data=None, bytes_data=None):
        """Handle auth token message and ping/pong keepalive."""
        if not text_data:
            return
        try:
            msg = json.loads(text_data)
        except Exception:
            return

        msg_type = msg.get("type")

        # ── Auth via first message ────────────────────────────────────────────
        if msg_type == "auth":
            if getattr(self, "_authenticated", False) or self.user_id:
                return  # already authed
            token_str = msg.get("token", "")
            if not token_str:
                await self.close(code=4001)
                return
            try:
                from channels.db import database_sync_to_async
                from rest_framework_simplejwt.authentication import JWTAuthentication

                jwt_auth = JWTAuthentication()
                validated = jwt_auth.get_validated_token(token_str.encode())
                user = await database_sync_to_async(jwt_auth.get_user)(validated)
                if not user or not user.is_authenticated:
                    await self.close(code=4001)
                    return
                self.user_id = str(user.id)
                self.group_name = f"notifications_{self.user_id}"
                self._authenticated = True
                await self.channel_layer.group_add(self.group_name, self.channel_name)
                await self.send(text_data=json.dumps({"type": "auth_ok"}))
                logger.info("WS authenticated (token): user=%s", self.user_id)
            except Exception as exc:
                logger.warning("WS token auth failed: %s", exc)
                await self.close(code=4001)
            return

        # ── Ping/pong keepalive ───────────────────────────────────────────────
        if msg_type == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

    # ── Group message handlers ────────────────────────────────────────────────

    async def notify(self, event):
        """Relay a notification pushed from the server to this WebSocket."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notification",
                    "data": event.get("data", {}),
                }
            )
        )
