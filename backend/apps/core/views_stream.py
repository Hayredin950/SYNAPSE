"""
SSE (Server-Sent Events) streaming endpoint for real-time content updates.

Async-compatible with Daphne/ASGI — uses asyncio.sleep instead of time.sleep
so it doesn't block the event loop.
"""
from __future__ import annotations

import asyncio
import json
import time
import logging

from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 20   # seconds between keepalive pings
CHECK_INTERVAL = 30       # seconds between content-count checks
MAX_DURATION = 5 * 60     # close connection after 5 min; client auto-reconnects


def _get_content_counts_sync() -> dict:
    """Return current content counts (synchronous DB calls)."""
    try:
        from apps.articles.models import Article
        from apps.repositories.models import Repository
        from apps.papers.models import ResearchPaper
        from apps.videos.models import Video
        from apps.tweets.models import Tweet
        from apps.trends.models import TechnologyTrend

        return {
            "articles": Article.objects.count(),
            "repos": Repository.objects.count(),
            "papers": ResearchPaper.objects.count(),
            "videos": Video.objects.count(),
            "tweets": Tweet.objects.count(),
            "trends": TechnologyTrend.objects.count(),
        }
    except Exception as exc:
        logger.warning("SSE: failed to get content counts: %s", exc)
        return {}


_get_content_counts = sync_to_async(_get_content_counts_sync, thread_sensitive=False)


def _validate_token(token: str) -> bool:
    """Validate a SimpleJWT access token — allow unauthenticated SSE."""
    if not token:
        return True
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        AccessToken(token)
        return True
    except Exception:
        # Expired or invalid token — still allow connection (SSE is read-only public data)
        return True


async def _async_event_stream():
    """
    Async generator for SSE events.
    Yields heartbeats every 20 s and content_update when counts change.
    Closes after MAX_DURATION so Daphne can cleanly free the connection.
    """
    start = time.monotonic()
    last_counts: dict = {}
    last_heartbeat = 0.0
    last_check = 0.0

    # Send initial snapshot
    try:
        counts = await _get_content_counts()
        last_counts = counts
        payload = json.dumps({"counts": counts, "changed": {}, "ts": int(time.time())})
        yield f"event: init\ndata: {payload}\n\n"
    except Exception as exc:
        logger.warning("SSE: init snapshot failed: %s", exc)
        yield f"event: init\ndata: {{}}\n\n"

    while True:
        # Close connection after max duration so client reconnects cleanly
        if time.monotonic() - start >= MAX_DURATION:
            yield "event: reconnect\ndata: {}\n\n"
            return

        await asyncio.sleep(1)
        now = time.time()

        # Heartbeat
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            yield f"event: heartbeat\ndata: {json.dumps({'ts': int(now)})}\n\n"
            last_heartbeat = now

        # Content check
        if now - last_check >= CHECK_INTERVAL:
            try:
                counts = await _get_content_counts()
                changed: dict = {}
                for key, val in counts.items():
                    old = last_counts.get(key, 0)
                    if val != old:
                        changed[key] = {"current": val, "previous": old, "new": val - old}

                if changed:
                    payload = json.dumps({"counts": counts, "changed": changed, "ts": int(now)})
                    yield f"event: content_update\ndata: {payload}\n\n"
                    last_counts = counts
            except Exception as exc:
                logger.warning("SSE: content check failed: %s", exc)
            last_check = now


@csrf_exempt
async def content_stream(request):
    """
    SSE endpoint — GET /api/v1/stream/

    Async view — compatible with Daphne/ASGI without blocking the event loop.
    Query params:
      token — optional JWT access token (EventSource can't set custom headers)
    """
    if request.method != "GET":
        from django.http import HttpResponse
        return HttpResponse("Method not allowed", status=405)

    token = request.GET.get("token", "")
    if not _validate_token(token):
        from django.http import HttpResponse
        return HttpResponse("Unauthorized", status=401)

    response = StreamingHttpResponse(
        _async_event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    response["Connection"] = "keep-alive"
    return response
