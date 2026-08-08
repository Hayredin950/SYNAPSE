import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# ── Langchain compatibility patch ─────────────────────────────────────────────
try:
    from langchain_core import exceptions as _lc_exc

    if not hasattr(_lc_exc, "ContextOverflowError"):

        class ContextOverflowError(_lc_exc.LangChainException):
            """Context window exceeded — compatibility shim."""

        _lc_exc.ContextOverflowError = ContextOverflowError
except Exception:
    pass
# ─────────────────────────────────────────────────────────────────────────────

from django.core.asgi import get_asgi_application

# Must call get_asgi_application() before importing channels/consumers
# so Django apps are fully loaded first.
django_asgi_app = get_asgi_application()

from apps.notifications.middleware import JwtAuthMiddleware
from apps.notifications.routing import websocket_urlpatterns
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator

# AllowedHostsOriginValidator rejects cross-origin WebSocket connections
# (frontend on a different domain than backend). OriginValidator allows
# explicit specification of permitted origins.
_frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
# Strip protocol for origin matching — OriginValidator checks the full origin
_ws_allowed_origins = [_frontend_url]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": OriginValidator(
            JwtAuthMiddleware(URLRouter(websocket_urlpatterns)),
            _ws_allowed_origins,
        ),
    }
)
