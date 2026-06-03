"""
YouTube Spider for SYNAPSE — uses yt-dlp flat-playlist mode (no API key, no quota, no hang).

Uses `yt-dlp --flat-playlist --dump-single-json` which returns search result metadata
instantly WITHOUT downloading video files or needing a JS runtime.

Strategy:
  1. For each search query, run yt-dlp with ytsearch<N>:<query>.
  2. Parse the returned JSON playlist entries (title, id, description, etc.)
  3. Apply a tech content filter to reject non-tech videos.
  4. Yield VideoItem for each passing video.
"""

import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone

import scrapy

from scraper.items import VideoItem

logger = logging.getLogger(__name__)

# Keywords that strongly indicate non-tech content — skip these videos.
NON_TECH_KEYWORDS = [
    "workout",
    "fitness",
    "gym",
    "yoga",
    "diet",
    "recipe",
    "cooking",
    "makeup",
    "beauty",
    "skincare",
    "fashion",
    "vlog",
    "travel",
    "prank",
    "challenge",
    "dance",
    "music video",
    "reaction",
    "unboxing",
    "asmr",
    "meditation",
    "relationship",
    "dating",
    "romance",
    "funny",
    "comedy",
    "sport",
    "football",
    "basketball",
    "soccer",
    "cricket",
    "movie review",
    "anime",
    "manga",
    "gaming highlights",
    "minecraft",
    "fortnite",
    "roblox",
    "weight loss",
    "bodybuilding",
    "real estate",
    "stock market tips",
]


class YouTubeSpider(scrapy.Spider):
    """
    YouTube spider using yt-dlp flat-playlist mode.

    Runs yt-dlp --flat-playlist --dump-single-json for each query, which
    returns search results as a JSON playlist object in under 5 seconds —
    no video download, no JS runtime, no quota.
    """

    name = "youtube"
    allowed_domains = []
    # Dummy start URL — overridden in start_requests via yt-dlp subprocess.
    start_urls = ["https://www.youtube.com"]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 0,
    }

    DEFAULT_QUERIES = [
        # Keep default small (8 queries max) to stay within the 300s task timeout
        # Each query takes ~15s via yt-dlp → 8 × 15s = 120s total (safe margin)
        "machine learning tutorial 2025",
        "large language models explained",
        "AI agents autonomous LLM",
        "open source AI tools 2025",
        "Django FastAPI Python tutorial",
        "Next.js React TypeScript tutorial",
        "Kubernetes Docker DevOps tutorial",
        "web security best practices",
    ]

    def __init__(self, queries=None, days_back=30, max_results=60, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Parse queries — may arrive as JSON string, newline-separated string, or list.
        if queries:
            if isinstance(queries, str):
                try:
                    parsed = json.loads(queries)
                    self.queries = parsed if isinstance(parsed, list) else [queries]
                except (json.JSONDecodeError, ValueError):
                    # Treat as newline-separated plain text
                    lines = [q.strip() for q in queries.splitlines() if q.strip()]
                    self.queries = lines if lines else self.DEFAULT_QUERIES
            else:
                self.queries = list(queries)
        else:
            self.queries = self.DEFAULT_QUERIES

        self.max_results = int(max_results)
        self.days_back = int(days_back)
        # Cap the number of queries so we never schedule more requests
        # than max_results — avoids wasted yt-dlp calls.
        max_queries = max(1, self.max_results)
        if len(self.queries) > max_queries:
            self.queries = self.queries[:max_queries]
        # How many yt-dlp results to request per query.
        num_queries = max(len(self.queries), 1)
        self.per_query = max(1, min(3, self.max_results // num_queries))
        # Track total items to respect max_results across all queries
        self.total_fetched = 0

        # Store user_id for personalization
        self.user_id = kwargs.get("user_id")

    # ── Scrapy entry point ──────────────────────────────────────────────────

    def start_requests(self):
        """Yield one dummy Scrapy request per query; actual work is in the callback."""
        for query in self.queries:
            yield scrapy.Request(
                url=f'https://www.youtube.com/results?search_query={query.replace(" ", "+")}',
                callback=self.fetch_with_ytdlp,
                cb_kwargs={"query": query},
                dont_filter=True,
            )

    # ── yt-dlp fetcher ──────────────────────────────────────────────────────

    def fetch_with_ytdlp(self, response, query):
        """
        Run yt-dlp in flat-playlist mode to get search results metadata.

        --flat-playlist  → do NOT visit individual video pages (no hang, no JS)
        --dump-single-json → output entire playlist as one JSON object
        --quiet / --no-warnings → suppress progress noise
        """
        ytdlp_bin = (
            shutil.which("yt-dlp")
            or "/usr/local/bin/yt-dlp"
            or "/home/appuser/.local/bin/yt-dlp"
        )

        n = self.per_query
        search_url = f"ytsearch{n}:{query}"

        try:
            result = subprocess.run(
                [
                    ytdlp_bin,
                    "--flat-playlist",
                    "--dump-single-json",
                    "--no-warnings",
                    "--quiet",
                    search_url,
                ],
                capture_output=True,
                text=True,
                timeout=20,  # flat-playlist is fast; 20s per query × 8 queries = 160s total
            )

            raw = (result.stdout or "").strip()
            if not raw:
                if result.stderr:
                    logger.warning(
                        f'yt-dlp no output for "{query}": {result.stderr[:200]}'
                    )
                return

            try:
                playlist = json.loads(raw)
            except json.JSONDecodeError as exc:
                logger.warning(f'yt-dlp JSON parse error for "{query}": {exc}')
                return

            entries = playlist.get("entries") or []
            logger.info(f'yt-dlp returned {len(entries)} entries for query "{query}"')

            for entry in entries:
                # Respect max_results limit across all queries
                if self.total_fetched >= self.max_results:
                    logger.info(
                        f"Reached max_results limit ({self.max_results}), closing spider"
                    )
                    self.crawler.engine.close_spider(self, "max_results_reached")
                    return

                item = self._entry_to_item(entry, query)
                if item is not None:
                    self.total_fetched += 1
                    yield item

        except subprocess.TimeoutExpired:
            logger.warning(f'yt-dlp timed out (30s) for query: "{query}"')
        except FileNotFoundError:
            logger.error(f"yt-dlp binary not found at {ytdlp_bin}")
        except Exception as exc:
            logger.error(f'yt-dlp error for query "{query}": {exc}')

    # ── Item builder ────────────────────────────────────────────────────────

    def _entry_to_item(self, entry: dict, query: str):
        """
        Convert a yt-dlp flat-playlist entry dict to a VideoItem.

        Returns None if the video should be skipped (non-tech or missing data).
        """
        video_id = entry.get("id", "")
        if not video_id:
            return None

        title = (entry.get("title") or "").strip()
        if not title:
            return None

        # ── Tech content filter ─────────────────────────────────────────
        title_lower = title.lower()
        desc_lower = (entry.get("description") or "").lower()
        combined = title_lower + " " + desc_lower[:200]

        for kw in NON_TECH_KEYWORDS:
            if kw in combined:
                logger.debug(
                    f'Skipping non-tech video: "{title[:60]}" (matched "{kw}")'
                )
                return None

        # ── Parse upload date ───────────────────────────────────────────
        upload_date_str = entry.get("upload_date", "") or ""
        try:
            published_at = (
                datetime.strptime(upload_date_str, "%Y%m%d")
                .replace(tzinfo=timezone.utc)
                .isoformat()
                if upload_date_str
                else datetime.now(timezone.utc).isoformat()
            )
        except ValueError:
            published_at = datetime.now(timezone.utc).isoformat()

        # ── Best thumbnail ──────────────────────────────────────────────
        thumbnails = entry.get("thumbnails") or []
        if thumbnails:
            # Pick the largest available thumbnail
            thumbnail_url = (
                thumbnails[-1].get("url", "")
                or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            )
        else:
            thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        # ── Build item ──────────────────────────────────────────────────
        item = VideoItem()
        item["youtube_id"] = video_id
        item["title"] = title[:500]
        item["description"] = (entry.get("description") or "")[:2000]
        item["channel_name"] = (entry.get("channel") or entry.get("uploader") or "")[
            :200
        ]
        item["channel_id"] = (
            entry.get("channel_id") or entry.get("uploader_id") or ""
        )[:100]
        item["published_at"] = published_at
        item["thumbnail_url"] = thumbnail_url
        item["duration_seconds"] = int(entry.get("duration") or 0)
        item["view_count"] = int(entry.get("view_count") or 0)
        item["like_count"] = int(entry.get("like_count") or 0)
        item["url"] = f"https://www.youtube.com/watch?v={video_id}"
        item["topics"] = [query]
        item["metadata"] = {
            "query": query,
            "source": "yt-dlp",
            "categories": entry.get("categories") or [],
            "tags": (entry.get("tags") or [])[:20],
            "channel_follower_count": entry.get("channel_follower_count") or 0,
            "language": entry.get("language") or "",
        }

        return item

    def parse(self, response):
        """Not used — yt-dlp handles all fetching."""
        pass
