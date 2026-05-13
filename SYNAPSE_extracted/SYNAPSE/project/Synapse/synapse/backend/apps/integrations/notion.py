"""
TASK-607-1: Notion Integration

OAuth flow, page import into RAG knowledge base, export research reports.

Required env vars:
    NOTION_CLIENT_ID        — from Notion integration settings
    NOTION_CLIENT_SECRET    — from Notion integration settings
    NOTION_REDIRECT_URI     — e.g. https://app.synapse.app/api/v1/integrations/notion/callback/
"""

from __future__ import annotations

import json
import logging
import os

import requests

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)

NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

User = get_user_model()


# ── OAuth helpers ─────────────────────────────────────────────────────────────


def get_authorization_url(state: str = "") -> str:
    """Return the Notion OAuth authorization URL."""
    client_id = getattr(
        settings, "NOTION_CLIENT_ID", os.environ.get("NOTION_CLIENT_ID", "")
    )
    redirect_uri = getattr(
        settings, "NOTION_REDIRECT_URI", os.environ.get("NOTION_REDIRECT_URI", "")
    )
    params = (
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&owner=user"
        f"&redirect_uri={redirect_uri}" + (f"&state={state}" if state else "")
    )
    return NOTION_AUTH_URL + params


def exchange_code_for_token(code: str) -> dict:
    """Exchange OAuth code for access token. Returns token dict."""
    client_id = getattr(
        settings, "NOTION_CLIENT_ID", os.environ.get("NOTION_CLIENT_ID", "")
    )
    client_secret = getattr(
        settings, "NOTION_CLIENT_SECRET", os.environ.get("NOTION_CLIENT_SECRET", "")
    )
    redirect_uri = getattr(
        settings, "NOTION_REDIRECT_URI", os.environ.get("NOTION_REDIRECT_URI", "")
    )

    resp = requests.post(
        NOTION_TOKEN_URL,
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        auth=(client_id, client_secret),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _notion_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ── Page import ───────────────────────────────────────────────────────────────


def list_pages(access_token: str, query: str = "") -> list[dict]:
    """Search Notion workspace for pages."""
    payload = {"filter": {"property": "object", "value": "page"}}
    if query:
        payload["query"] = query
    resp = requests.post(
        f"{NOTION_API_BASE}/search",
        headers=_notion_headers(access_token),
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def get_page_content(access_token: str, page_id: str) -> str:
    """Fetch plain-text content of a Notion page (up to 100 blocks)."""
    resp = requests.get(
        f"{NOTION_API_BASE}/blocks/{page_id}/children?page_size=100",
        headers=_notion_headers(access_token),
        timeout=15,
    )
    resp.raise_for_status()
    blocks = resp.json().get("results", [])
    lines: list[str] = []
    for block in blocks:
        btype = block.get("type", "")
        bdata = block.get(btype, {})
        rich_text = bdata.get("rich_text", [])
        text = " ".join(
            t.get("plain_text", "") for t in rich_text if isinstance(t, dict)
        )
        if text:
            lines.append(text)
    return "\n".join(lines)


def import_page_to_rag(access_token: str, page_id: str, user) -> bool:
    """
    Import a Notion page into the Synapse RAG knowledge base.
    Returns True on success.
    """
    try:
        # Fetch page metadata
        page_resp = requests.get(
            f"{NOTION_API_BASE}/pages/{page_id}",
            headers=_notion_headers(access_token),
            timeout=15,
        )
        page_resp.raise_for_status()
        page = page_resp.json()

        # Extract title
        title = "Untitled"
        props = page.get("properties", {})
        for prop_name in ("Name", "Title", "title"):
            if prop_name in props:
                rt = props[prop_name].get("title", [])
                if rt:
                    title = rt[0].get("plain_text", "Untitled")
                    break

        content = get_page_content(access_token, page_id)
        if not content:
            return False

        # Save as KnowledgeNode for the knowledge graph
        from apps.core.models import KnowledgeNode  # noqa: PLC0415

        node, created = KnowledgeNode.objects.get_or_create(
            name=title[:300],
            entity_type="concept",
            defaults={
                "description": content[:500],
                "source_ids": [f"notion:{page_id}"],
                "metadata": {
                    "notion_page_id": page_id,
                    "source": "notion",
                    "user_id": str(user.pk),
                },
            },
        )
        if not created:
            node.description = content[:500]
            node.mention_count += 1
            node.save(update_fields=["description", "mention_count", "updated_at"])

        logger.info("Imported Notion page '%s' for user %s", title, user.pk)
        return True

    except Exception as exc:
        logger.error("Notion import failed for page %s: %s", page_id, exc)
        return False


# ── Export to Notion ──────────────────────────────────────────────────────────


def export_report_to_notion(
    access_token: str, parent_page_id: str, title: str, content: str
) -> str | None:
    """
    Create a new Notion page with the given markdown content.
    Returns the created page ID or None on failure.
    """
    # Convert content into simple paragraph blocks
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": para[:2000]}}]
            },
        }
        for para in paragraphs[:50]
    ]

    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "properties": {
            "title": {"title": [{"type": "text", "text": {"content": title[:255]}}]}
        },
        "children": children,
    }

    try:
        resp = requests.post(
            f"{NOTION_API_BASE}/pages",
            headers=_notion_headers(access_token),
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as exc:
        logger.error("Notion export failed: %s", exc)
        return None
