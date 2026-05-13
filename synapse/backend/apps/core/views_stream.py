"""
SSE (Server-Sent Events) streaming endpoint for real-time content updates.

Streams live content counts to the dashboard so the UI can show "new articles" 
notifications without polling.
"""
from __future__ import annotations

import json
import time
import logging

from django.http import StreamingHttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


def _get_content_counts() -> dict:
    """Return current content counts across all scraped content types."""
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


def _validate_token(token: str) -> bool:
    """Validate a SimpleJWT access token (permissive — returns True if no token given)."""
    if not token:
        return True  # allow unauthenticated SSE for now
    try:
        from rest_framework_simplejwt.tokens import AccessToken

        AccessToken(token)
        return True
    except Exception:
        return False


def _event_stream():
    """
    Generator that yields SSE-formatted events indefinitely.

    Events:
      heartbeat      — every 15 s to keep the connection alive
      content_update — whenever scraped content counts change (checked every 30 s)
      init           — sent immediately with current counts
    """
    last_counts: dict = {}
    last_heartbeat: float = 0.0
    last_check: float = 0.0
    HEARTBEAT_INTERVAL = 15  # seconds
    CHECK_INTERVAL = 30  # seconds

    # Send initial snapshot immediately
    counts = _get_content_counts()
    last_counts = counts
    last_check = time.time()
    payload = json.dumps({"counts": counts, "changed": {}, "ts": int(time.time())})
    yield f"event: init\ndata: {payload}\n\n"

    while True:
        now = time.time()

        # Heartbeat — keeps the TCP connection alive through proxies
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            yield f"event: heartbeat\ndata: {json.dumps({'ts': int(now)})}\n\n"
            last_heartbeat = now

        # Content check
        if now - last_check >= CHECK_INTERVAL:
            counts = _get_content_counts()
            changed: dict = {}
            for key, val in counts.items():
                old = last_counts.get(key, 0)
                if val != old:
                    changed[key] = {"current": val, "previous": old, "new": val - old}

            if changed:
                payload = json.dumps(
                    {"counts": counts, "changed": changed, "ts": int(now)}
                )
                yield f"event: content_update\ndata: {payload}\n\n"
                last_counts = counts

            last_check = now

        time.sleep(1)


@csrf_exempt
@require_GET
def content_stream(request):
    """
    SSE endpoint — GET /api/v1/stream/

    Query params:
      token — optional JWT access token (EventSource can't set headers)
    """
    token = request.GET.get("token", "")
    if not _validate_token(token):
        from django.http import HttpResponse
        return HttpResponse("Unauthorized", status=401)

    response = StreamingHttpResponse(
        _event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    response["Connection"] = "keep-alive"
    return response
