"""
TASK-605-B4: API Key management endpoints.

GET    /api/v1/keys/       — list user's API keys (prefix only, no full key)
POST   /api/v1/keys/       — create new key (returns full key ONCE)
DELETE /api/v1/keys/{id}/  — revoke key (set is_active=False)
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import APIKey


class APIKeyListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        keys = APIKey.objects.filter(user=request.user).order_by("-created_at")
        data = [
            {
                "id": str(k.id),
                "name": k.name,
                "key_prefix": k.key_prefix,
                "scopes": k.scopes,
                "last_used": k.last_used.isoformat() if k.last_used else None,
                "is_active": k.is_active,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "created_at": k.created_at.isoformat(),
            }
            for k in keys
        ]
        return Response({"success": True, "data": data})

    def post(self, request: Request) -> Response:
        name = (request.data.get("name") or "").strip()
        scopes = request.data.get("scopes", [])

        if not name:
            return Response(
                {"success": False, "error": "name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(name) > 100:
            return Response(
                {"success": False, "error": "name too long"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(scopes, list):
            return Response(
                {"success": False, "error": "scopes must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Limit to 10 active keys per user
        if APIKey.objects.filter(user=request.user, is_active=True).count() >= 10:
            return Response(
                {"success": False, "error": "Maximum of 10 active API keys allowed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key, raw_key = APIKey.create_key(request.user, name=name, scopes=scopes)
        return Response(
            {
                "success": True,
                "data": {
                    "id": str(api_key.id),
                    "name": api_key.name,
                    "key": raw_key,  # ← shown ONCE; not stored
                    "key_prefix": api_key.key_prefix,
                    "scopes": api_key.scopes,
                    "created_at": api_key.created_at.isoformat(),
                },
                "warning": "Copy your API key now — it will not be shown again.",
            },
            status=status.HTTP_201_CREATED,
        )


class APIKeyRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, pk) -> Response:
        try:
            api_key = APIKey.objects.get(pk=pk, user=request.user)
        except APIKey.DoesNotExist:
            return Response({"success": False, "error": "Not found"}, status=404)
        api_key.is_active = False
        api_key.save(update_fields=["is_active"])
        return Response({"success": True, "data": {"message": "API key revoked"}})
