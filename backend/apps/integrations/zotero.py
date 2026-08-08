"""
TASK-607-4: Zotero Integration

Connect via Zotero API key, import library into RAG, auto-update on new items.

Required env vars / user settings:
    ZOTERO_API_KEY     — user's Zotero API key
    ZOTERO_USER_ID     — user's Zotero user/group ID
"""

from __future__ import annotations

import logging
from typing import Generator

import requests

logger = logging.getLogger(__name__)

ZOTERO_API_BASE = "https://api.zotero.org"


# ── API client ────────────────────────────────────────────────────────────────


class ZoteroClient:
    """Minimal Zotero API v3 client."""

    def __init__(self, api_key: str, user_id: str, is_group: bool = False):
        self.api_key = api_key
        self.user_id = user_id
        self.is_group = is_group
        self._base = (
            f"{ZOTERO_API_BASE}/groups/{user_id}"
            if is_group
            else f"{ZOTERO_API_BASE}/users/{user_id}"
        )
        self._headers = {
            "Zotero-API-Key": api_key,
            "Zotero-API-Version": "3",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> requests.Response:
        resp = requests.get(
            f"{self._base}{path}",
            headers=self._headers,
            params=params or {},
            timeout=20,
        )
        resp.raise_for_status()
        return resp

    def validate_credentials(self) -> bool:
        """Check API key + user_id are valid."""
        try:
            self._get("/collections", {"limit": 1})
            return True
        except Exception:
            return False

    def get_library_version(self) -> int:
        """Return current library version (for incremental sync)."""
        resp = self._get("/items", {"limit": 1, "format": "json"})
        return int(resp.headers.get("Last-Modified-Version", 0))

    def iter_items(
        self, since_version: int = 0, limit: int = 100
    ) -> Generator[list[dict], None, None]:
        """
        Yield pages of Zotero items.
        Uses `since` for incremental sync when since_version > 0.
        """
        start = 0
        params: dict = {"limit": limit, "format": "json", "include": "data"}
        if since_version:
            params["since"] = since_version

        while True:
            params["start"] = start
            resp = self._get("/items", params)
            items = resp.json()
            if not items:
                break
            yield items
            if len(items) < limit:
                break
            start += limit


# ── Import pipeline ───────────────────────────────────────────────────────────


def _extract_item_data(item: dict) -> dict | None:
    """Extract relevant fields from a Zotero item for RAG import."""
    data = item.get("data", {})
    item_type = data.get("itemType", "")

    # Skip attachments, notes, web pages
    if item_type in ("attachment", "note", "webpage"):
        return None

    title = data.get("title", "").strip()
    if not title:
        return None

    abstract = data.get("abstractNote", "").strip()
    authors = [
        f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
        for c in data.get("creators", [])
        if c.get("creatorType") == "author"
    ]
    url = data.get("url", "") or data.get("DOI", "")
    year = data.get("date", "")[:4] if data.get("date") else ""
    tags = [t.get("tag", "") for t in data.get("tags", []) if t.get("tag")]

    return {
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "url": url,
        "year": year,
        "tags": tags,
        "type": item_type,
        "key": data.get("key", ""),
    }


def import_library(zotero_client: ZoteroClient, user, since_version: int = 0) -> dict:
    """
    Import Zotero library items into the Synapse knowledge base.
    Creates KnowledgeNodes for each paper/book and author edges.

    Returns {'imported': N, 'skipped': M, 'new_version': V}
    """
    from apps.core.models import KnowledgeEdge, KnowledgeNode  # noqa: PLC0415

    imported = 0
    skipped = 0
    new_version = zotero_client.get_library_version()

    for page in zotero_client.iter_items(since_version=since_version):
        for raw_item in page:
            item_data = _extract_item_data(raw_item)
            if not item_data:
                skipped += 1
                continue

            # Create/update paper node
            paper_node, _ = KnowledgeNode.objects.get_or_create(
                name=item_data["title"][:300],
                entity_type="paper",
                defaults={
                    "description": item_data["abstract"][:500],
                    "source_ids": [f"zotero:{item_data['key']}"],
                    "metadata": {
                        "source": "zotero",
                        "url": item_data["url"],
                        "year": item_data["year"],
                        "type": item_data["type"],
                        "tags": item_data["tags"],
                        "user_id": str(user.pk),
                    },
                },
            )

            # Create author nodes + edges
            for author_name in item_data["authors"][:5]:
                if not author_name:
                    continue
                author_node, _ = KnowledgeNode.objects.get_or_create(
                    name=author_name[:300],
                    entity_type="author",
                    defaults={"source_ids": [f"zotero:{item_data['key']}"]},
                )
                KnowledgeEdge.objects.get_or_create(
                    source=paper_node,
                    target=author_node,
                    relation_type="authored_by",
                    defaults={"weight": 1.0},
                )

            imported += 1

    logger.info(
        "Zotero import: %d imported, %d skipped for user %s", imported, skipped, user.pk
    )
    return {"imported": imported, "skipped": skipped, "new_version": new_version}


# ── Incremental sync check ────────────────────────────────────────────────────


def check_for_new_items(zotero_client: ZoteroClient, last_version: int) -> bool:
    """Return True if the library has been updated since last_version."""
    current_version = zotero_client.get_library_version()
    return current_version > last_version
