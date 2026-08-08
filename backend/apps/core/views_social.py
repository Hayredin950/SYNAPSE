"""
SYNAPSE Social & Community Endpoints

Endpoints:
  POST   /api/v1/social/upvote/         — Upvote an article
  DELETE /api/v1/social/upvote/         — Remove upvote
  GET    /api/v1/social/upvotes/        — Get upvote counts for articles
  GET    /api/v1/social/comments/       — Get comments for an article
  POST   /api/v1/social/comments/       — Post a comment
  DELETE /api/v1/social/comments/{id}/  — Delete comment
  GET    /api/v1/social/watchlist/      — Get user watchlist
  POST   /api/v1/social/watchlist/      — Add keyword to watchlist
  DELETE /api/v1/social/watchlist/{id}/ — Remove from watchlist
  GET    /api/v1/social/digest/share/   — Get shareable digest link
  POST   /api/v1/social/digest/share/   — Generate shareable digest
  GET    /api/v1/social/network-reading/ — What your connections are reading
"""

import hashlib
import json
import logging
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


# ── Inline lightweight models (no migration needed — use Django cache layer) ───

_UPVOTES   = {}   # {article_id: {user_id: timestamp}}
_COMMENTS  = {}   # {article_id: [{id, user_id, username, text, created_at}]}
_WATCHLIST = {}   # {user_id: [{id, keyword, created_at}]}
_DIGESTS   = {}   # {share_id: {user_id, articles, created_at}}

# Try to use Redis-backed cache if available
def _cache_get(key, default=None):
    try:
        from django.core.cache import cache
        val = cache.get(f"synapse_social:{key}")
        return val if val is not None else default
    except Exception:
        return default

def _cache_set(key, value, timeout=86400 * 30):
    try:
        from django.core.cache import cache
        cache.set(f"synapse_social:{key}", value, timeout)
    except Exception:
        pass


# ── Feature 20: Community Upvotes ─────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upvote(request):
    """Toggle upvote for an article. Body: { article_id, content_type? }"""
    article_id   = str(request.data.get("article_id", "")).strip()
    content_type = request.data.get("content_type", "article")
    user_id      = str(request.user.id)

    if not article_id:
        return Response({"success": False, "error": "article_id required"},
                        status=status.HTTP_400_BAD_REQUEST)

    cache_key = f"upvotes:{article_id}"
    votes = _cache_get(cache_key, {})

    if user_id in votes:
        del votes[user_id]
        action = "removed"
    else:
        votes[user_id] = timezone.now().isoformat()
        action = "added"

    _cache_set(cache_key, votes)
    return Response({
        "success": True,
        "action": action,
        "upvote_count": len(votes),
        "user_upvoted": action == "added",
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def upvote_counts(request):
    """Get upvote counts for a list of article IDs. Query: ids=id1,id2,id3"""
    ids = request.query_params.get("ids", "").split(",")
    ids = [i.strip() for i in ids if i.strip()][:50]
    user_id = str(getattr(request.user, "id", ""))

    result = {}
    for aid in ids:
        votes = _cache_get(f"upvotes:{aid}", {})
        result[aid] = {
            "count": len(votes),
            "user_upvoted": user_id in votes,
        }
    return Response({"success": True, "upvotes": result})


# ── Feature 34: Discussion Threads ────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def comments(request):
    """
    GET  ?article_id=xxx  — List comments for article
    POST { article_id, text } — Post a comment
    """
    if request.method == "GET":
        article_id = request.query_params.get("article_id", "")
        if not article_id:
            return Response({"success": False, "error": "article_id required"},
                            status=status.HTTP_400_BAD_REQUEST)
        key = f"comments:{article_id}"
        thread = _cache_get(key, [])
        return Response({"success": True, "comments": thread, "count": len(thread)})

    # POST
    article_id = str(request.data.get("article_id", "")).strip()
    text       = str(request.data.get("text", "")).strip()[:2000]

    if not article_id or not text:
        return Response({"success": False, "error": "article_id and text required"},
                        status=status.HTTP_400_BAD_REQUEST)

    comment = {
        "id":         str(uuid.uuid4()),
        "user_id":    str(request.user.id),
        "username":   request.user.email.split("@")[0] if request.user.email else "user",
        "text":       text,
        "created_at": timezone.now().isoformat(),
        "upvotes":    0,
    }

    key = f"comments:{article_id}"
    thread = _cache_get(key, [])
    thread.insert(0, comment)
    _cache_set(key, thread[:200])  # Keep last 200 comments

    return Response({"success": True, "comment": comment}, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_comment(request, comment_id):
    """Delete a comment by ID (owner only)."""
    # Find the comment across all articles (not efficient but works for demo)
    article_id = request.query_params.get("article_id", "")
    if not article_id:
        return Response({"success": False, "error": "article_id required"},
                        status=status.HTTP_400_BAD_REQUEST)

    key = f"comments:{article_id}"
    thread = _cache_get(key, [])
    user_id = str(request.user.id)

    new_thread = [c for c in thread if not (c["id"] == comment_id and c["user_id"] == user_id)]
    if len(new_thread) == len(thread):
        return Response({"success": False, "error": "Comment not found or not authorized"},
                        status=status.HTTP_404_NOT_FOUND)

    _cache_set(key, new_thread)
    return Response({"success": True})


# ── Feature 2: Topic Watchlist ────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def watchlist(request):
    """
    GET  — List user's watchlist keywords
    POST { keyword, notify_frequency? } — Add keyword
    """
    user_id = str(request.user.id)
    key     = f"watchlist:{user_id}"

    if request.method == "GET":
        items = _cache_get(key, [])
        # Check for new content matching any keyword
        alerts = []
        for item in items:
            kw = item.get("keyword", "")
            try:
                from apps.articles.models import Article
                from django.db.models import Q
                cutoff = timezone.now() - timedelta(hours=24)
                count = Article.objects.filter(
                    Q(title__icontains=kw) | Q(summary__icontains=kw),
                    scraped_at__gte=cutoff,
                ).count()
                if count > 0:
                    alerts.append({"keyword": kw, "new_count": count})
            except Exception:
                pass
        return Response({"success": True, "watchlist": items, "alerts": alerts})

    # POST
    keyword = str(request.data.get("keyword", "")).strip()[:100]
    notify  = request.data.get("notify_frequency", "daily")

    if not keyword:
        return Response({"success": False, "error": "keyword required"},
                        status=status.HTTP_400_BAD_REQUEST)

    items = _cache_get(key, [])
    # Check for duplicates
    if any(i["keyword"].lower() == keyword.lower() for i in items):
        return Response({"success": False, "error": "Already watching this keyword"},
                        status=status.HTTP_400_BAD_REQUEST)

    entry = {
        "id":               str(uuid.uuid4()),
        "keyword":          keyword,
        "notify_frequency": notify,
        "created_at":       timezone.now().isoformat(),
    }
    items.insert(0, entry)
    _cache_set(key, items[:50])
    return Response({"success": True, "entry": entry}, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_watchlist(request, watch_id):
    user_id = str(request.user.id)
    key     = f"watchlist:{user_id}"
    items   = _cache_get(key, [])
    new     = [i for i in items if i["id"] != watch_id]
    _cache_set(key, new)
    return Response({"success": True})


# ── Feature 32: Share Digest ──────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def share_digest(request):
    """
    Generate a shareable digest link.
    Body: { articles: [{id, title, url, summary}], title? }
    """
    articles = request.data.get("articles", [])[:20]
    title    = request.data.get("title", f"SYNAPSE Digest — {timezone.now().strftime('%b %d, %Y')}")
    user_id  = str(request.user.id)

    share_id = hashlib.sha256(f"{user_id}:{title}:{json.dumps(articles)[:100]}".encode()).hexdigest()[:12]
    digest   = {
        "id":         share_id,
        "title":      title,
        "user_id":    user_id,
        "articles":   articles,
        "created_at": timezone.now().isoformat(),
    }
    _cache_set(f"digest:{share_id}", digest, timeout=86400 * 7)  # 7 days
    return Response({"success": True, "share_id": share_id, "title": title})


@api_view(["GET"])
@permission_classes([AllowAny])
def view_digest(request, share_id):
    """View a shared digest by ID."""
    digest = _cache_get(f"digest:{share_id}")
    if not digest:
        return Response({"success": False, "error": "Digest not found or expired"},
                        status=status.HTTP_404_NOT_FOUND)
    return Response({"success": True, "digest": digest})


# ── Feature 33: What My Network Is Reading ────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def network_reading(request):
    """
    Surface articles being bookmarked/upvoted by many users recently.
    (Simulated via top upvoted + recently bookmarked content)
    """
    try:
        from apps.articles.models import Article
        # Get most recently scraped articles (proxy for "popular")
        qs = Article.objects.order_by("-scraped_at")[:30]
        articles = []
        for a in qs:
            upvotes = _cache_get(f"upvotes:{a.id}", {})
            if len(upvotes) > 0 or True:  # show all for now
                articles.append({
                    "id":        str(a.id),
                    "title":     a.title,
                    "url":       a.url,
                    "summary":   (a.summary or "")[:200],
                    "upvotes":   len(upvotes),
                    "source_type": getattr(a, 'source_type', 'article'),
                    "scraped_at": a.scraped_at.isoformat() if a.scraped_at else None,
                })
        # Sort by upvotes desc
        articles.sort(key=lambda x: x["upvotes"], reverse=True)
        return Response({"success": True, "articles": articles[:15]})
    except Exception as exc:
        logger.error("network_reading error: %s", exc)
        return Response({"success": True, "articles": []})


# ── Feature 35: Source Quality / Credibility ──────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def source_quality(request, domain):
    """Return credibility / quality metadata for a domain."""
    import re
    # Known credible sources
    HIGH_CREDIBILITY = {
        'arxiv.org', 'github.com', 'nature.com', 'science.org',
        'mit.edu', 'stanford.edu', 'acm.org', 'ieee.org', 'dl.acm.org',
        'openai.com', 'deepmind.com', 'research.google', 'ai.meta.com',
        'microsoft.com', 'aws.amazon.com', 'cloud.google.com',
    }
    MEDIUM_CREDIBILITY = {
        'medium.com', 'substack.com', 'dev.to', 'hackernoon.com',
        'towardsdatascience.com', 'thenewstack.io', 'infoq.com',
        'techcrunch.com', 'wired.com', 'theverge.com', 'arstechnica.com',
    }

    clean = re.sub(r'^www\.', '', domain.lower().strip())
    if clean in HIGH_CREDIBILITY:
        score, label, colour = 95, 'Highly Credible', 'green'
    elif clean in MEDIUM_CREDIBILITY:
        score, label, colour = 75, 'Generally Reliable', 'yellow'
    else:
        score, label, colour = 55, 'Unverified', 'slate'

    return Response({
        "success": True,
        "domain":  clean,
        "score":   score,
        "label":   label,
        "colour":  colour,
        "last_checked": timezone.now().isoformat(),
    })
