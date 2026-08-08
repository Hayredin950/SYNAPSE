"""
TASK-607-3: Obsidian Integration

Accept vault file uploads, parse Markdown notes, embed into knowledge base,
and write AI-generated summaries back as new notes.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import IO, Generator

logger = logging.getLogger(__name__)

# ── Markdown parsing ──────────────────────────────────────────────────────────


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Extract YAML frontmatter from an Obsidian note.
    Returns (metadata_dict, body_without_frontmatter).
    """
    metadata: dict = {}
    body = content

    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            yaml_block = content[3:end].strip()
            body = content[end + 4 :].strip()
            # Minimal YAML parsing (key: value pairs only)
            for line in yaml_block.splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    metadata[key.strip()] = value.strip().strip('"')
    return metadata, body


def extract_wikilinks(content: str) -> list[str]:
    """Extract [[wikilinks]] from Obsidian note content."""
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)


def extract_tags(content: str, frontmatter: dict) -> list[str]:
    """Extract #tags from content and frontmatter tags field."""
    inline_tags = re.findall(r"#([A-Za-z][A-Za-z0-9_/-]+)", content)
    fm_tags = frontmatter.get("tags", "")
    if isinstance(fm_tags, str):
        fm_tags = [t.strip() for t in fm_tags.strip("[]").split(",") if t.strip()]
    elif not isinstance(fm_tags, list):
        fm_tags = []
    return list(set(inline_tags + fm_tags))


def clean_content(content: str) -> str:
    """Strip wikilinks, tags, and markdown syntax for clean text."""
    # Replace [[wikilinks]] with their display text
    content = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", content)
    content = re.sub(r"\[\[([^\]]+)\]\]", r"\1", content)
    # Remove markdown headings, bold, italic, code
    content = re.sub(r"^#{1,6}\s+", "", content, flags=re.MULTILINE)
    content = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", content)
    content = re.sub(r"`[^`]+`", "", content)
    content = re.sub(r"```[\s\S]*?```", "", content)
    return content.strip()


# ── Import pipeline ───────────────────────────────────────────────────────────


def parse_markdown_file(filename: str, content: str) -> dict:
    """
    Parse a single Obsidian markdown file.
    Returns structured note data.
    """
    frontmatter, body = parse_frontmatter(content)
    title = frontmatter.get("title") or Path(filename).stem.replace("-", " ").replace(
        "_", " "
    )
    clean_body = clean_content(body)
    wikilinks = extract_wikilinks(body)
    tags = extract_tags(body, frontmatter)

    return {
        "title": title,
        "body": clean_body,
        "frontmatter": frontmatter,
        "wikilinks": wikilinks,
        "tags": tags,
        "filename": filename,
    }


def import_vault_notes(notes: list[dict], user) -> dict:
    """
    Import a list of parsed Obsidian notes into the knowledge graph.
    Creates KnowledgeNodes for notes and KnowledgeEdges for wikilinks.

    Returns {'imported': N, 'edges_created': M}
    """
    from apps.core.models import KnowledgeEdge, KnowledgeNode  # noqa: PLC0415

    node_map: dict[str, KnowledgeNode] = {}
    imported = 0

    # First pass: create/update nodes
    for note in notes:
        if not note.get("body"):
            continue
        name = note["title"][:300]
        if not name:
            continue
        node, _ = KnowledgeNode.objects.get_or_create(
            name=name,
            entity_type="concept",
            defaults={
                "description": note["body"][:500],
                "source_ids": [f'obsidian:{note["filename"]}'],
                "metadata": {
                    "source": "obsidian",
                    "filename": note["filename"],
                    "tags": note["tags"],
                    "user_id": str(user.pk),
                },
            },
        )
        node_map[note["title"]] = node
        node_map[note["filename"]] = node
        imported += 1

    # Second pass: create wikilink edges
    edges_created = 0
    for note in notes:
        src_node = node_map.get(note["title"])
        if not src_node:
            continue
        for link_title in note.get("wikilinks", []):
            tgt_node = node_map.get(link_title)
            if tgt_node and tgt_node.pk != src_node.pk:
                _, created = KnowledgeEdge.objects.get_or_create(
                    source=src_node,
                    target=tgt_node,
                    relation_type="related_to",
                    defaults={"weight": 1.0, "evidence": [{"source": "obsidian"}]},
                )
                if created:
                    edges_created += 1

    logger.info(
        "Obsidian import: %d notes, %d edges for user %s",
        imported,
        edges_created,
        user.pk,
    )
    return {"imported": imported, "edges_created": edges_created}


# ── Export AI summaries back to Obsidian format ────────────────────────────────


def generate_obsidian_note(
    title: str, content: str, tags: list[str] | None = None
) -> str:
    """
    Generate an Obsidian-compatible Markdown note with frontmatter.
    Can be downloaded and placed in the user's vault.
    """
    from django.utils import timezone  # noqa: PLC0415

    date_str = timezone.now().strftime("%Y-%m-%d")
    tag_list = ", ".join(f'"{t}"' for t in (tags or ["synapse", "ai-generated"]))

    frontmatter = f"""---
title: "{title}"
date: {date_str}
tags: [{tag_list}]
source: synapse-ai
---

"""
    return frontmatter + content
