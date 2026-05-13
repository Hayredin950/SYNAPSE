"""
JWT authentication middleware for Django Channels WebSocket connections.
Reads the token from the Authorization header or ?token= query parameter.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def get_user_from_token(token: str):
    """Validate a JWT access token and return the corresponding user."""
    try:
        from rest_framework_simplejwt.tokens import AccessToken

        from django.contrib.auth import get_user_model

        User = get_user_model()
        validated = AccessToken(token)
        return User.objects.get(id=validated["user_id"])
    except Exception:
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """
    Resolves the JWT token from:
      1. Authorization: Bearer <token>  header
      2. ?token=<token>                 query parameter
    """

    async def __call__(self, scope, receive, send):
        token = None

        # 1. Try headers (bytes)
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

        # 2. Fall back to query string
        if not token:
            qs = parse_qs(scope.get("query_string", b"").decode())
            token_list = qs.get("token", [])
            if token_list:
                token = token_list[0]

        scope["user"] = await get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
