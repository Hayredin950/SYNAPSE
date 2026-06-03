"""
HackerNews Spider for SYNAPSE — AI-powered tech intelligence platform

Fetches stories from Hacker News using the Firebase API.
Supports different story types: top, new, best, ask, show, job.
Populates ArticleItem with:
  - Story metadata (title, URL, score, author)
  - Published timestamp (converted to ISO 8601 UTC)
  - Content (HTML stripped for Ask/Show HN)
  - Rich metadata (HN ID, score, comment count, story type)
  - Consistent source attribution

Handles API rate limiting gracefully and skips non-story types.
For Ask/Show HN without URLs, uses HN discussion URL.
"""

import logging
from datetime import datetime, timezone
from html.parser import HTMLParser

import scrapy
from bs4 import BeautifulSoup

from scraper.items import ArticleItem

logger = logging.getLogger(__name__)


class HTMLStripper(HTMLParser):
    """Simple HTML tag stripper."""

    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, data):
        self.fed.append(data)

    def get_data(self):
        return "".join(self.fed)


def strip_html(html_str):
    """Strip HTML tags from string."""
    if not html_str:
        return ""
    s = HTMLStripper()
    try:
        s.feed(html_str)
        return s.get_data()
    except Exception:
        # Fallback to BeautifulSoup if HTMLParser fails
        try:
            return BeautifulSoup(html_str, "html.parser").get_text()
        except Exception:
            return html_str


class HackerNewsSpider(scrapy.Spider):
    """
    HackerNews Firebase API spider for discovering tech stories.

    Attributes:
        name: Spider identifier ('hackernews')
        allowed_domains: HN API and discussion domains
        custom_settings: Rate limiting and request configuration
    """

    name = "hackernews"
    allowed_domains = ["hacker-news.firebaseio.com", "news.ycombinator.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.3,
        "CONCURRENT_REQUESTS": 16,
        "ROBOTSTXT_OBEY": False,
    }

    VALID_STORY_TYPES = ["top", "new", "best", "ask", "show", "job"]

    def __init__(self, *args, **kwargs):
        super(HackerNewsSpider, self).__init__(*args, **kwargs)

        # Parse CLI arguments
        self.story_type = kwargs.get("story_type", "top").lower()
        if self.story_type not in self.VALID_STORY_TYPES:
            logger.warning(
                f'Invalid story_type "{self.story_type}". '
                f'Using "top". Valid choices: {", ".join(self.VALID_STORY_TYPES)}'
            )
            self.story_type = "top"

        self.limit = int(kwargs.get("limit", 100))
        self.limit = min(max(self.limit, 1), 500)  # Clamp 1-500

        # Store user_id for personalization
        self.user_id = kwargs.get("user_id")

        self.base_url = "https://hacker-news.firebaseio.com/v0"

    def start_requests(self):
        """Fetch story IDs list."""
        url = f"{self.base_url}/{self.story_type}stories.json"

        yield scrapy.Request(
            url,
            callback=self.parse_story_ids,
            errback=self.handle_error,
        )

    def parse_story_ids(self, response):
        """
        Parse story IDs list and fetch each story in parallel.

        Args:
            response: Scrapy response from story IDs endpoint

        Yields:
            Requests to fetch individual story items
        """
        try:
            story_ids = response.json()
        except Exception as e:
            logger.error(f"Failed to parse story IDs: {e}")
            return

        if not story_ids:
            logger.info(f"No stories found for type: {self.story_type}")
            return

        # Limit to requested count
        story_ids = story_ids[: self.limit]

        logger.info(f'Fetching {len(story_ids)} stories of type "{self.story_type}"')

        # Fetch each story in parallel
        for story_id in story_ids:
            url = f"{self.base_url}/item/{story_id}.json"

            yield scrapy.Request(
                url,
                callback=self.parse_item,
                errback=self.handle_error,
                meta={"story_id": story_id},
            )

    def parse_item(self, response):
        """
        Parse individual story item and yield ArticleItem.

        Args:
            response: Scrapy response from item endpoint

        Yields:
            ArticleItem: Populated with story data, or None if skipped
        """
        story_id = response.meta.get("story_id")

        try:
            item_data = response.json()
        except Exception as e:
            logger.error(f"Failed to parse item {story_id}: {e}")
            return

        # Skip non-story types (comments, polls, etc.)
        item_type = item_data.get("type", "")
        if item_type not in ["story", "poll"]:
            return

        # Skip polls (they have no URL and text field is optional)
        if item_type == "poll":
            return

        url = item_data.get("url")
        text = item_data.get("text", "")
        title = item_data.get("title", "")

        # For Ask/Show HN without URL, use discussion URL
        if not url:
            if title.startswith(("Ask HN:", "Show HN:")):
                url = f"https://news.ycombinator.com/item?id={story_id}"
            else:
                # Skip stories without URLs
                return

        # Parse content (strip HTML for Ask/Show HN text field)
        content = strip_html(text) if text else ""

        # Convert Unix timestamp to ISO 8601 UTC
        timestamp = item_data.get("time", 0)
        try:
            published_at = datetime.fromtimestamp(
                timestamp, tz=timezone.utc
            ).isoformat()
        except Exception:
            published_at = ""

        # Build metadata
        metadata = {
            "hn_id": story_id,
            "score": item_data.get("score", 0),
            "comments": item_data.get("descendants", 0),
            "type": item_type,
            "kids_count": len(item_data.get("kids", [])),
        }

        article_item = ArticleItem(
            title=title,
            url=url,
            content=content,
            author=item_data.get("by", ""),
            published_at=published_at,
            source_name="Hacker News",
            source_url="https://news.ycombinator.com",
            source_type="news",
            tags=[],
            metadata=metadata,
        )

        yield article_item

    def handle_error(self, failure):
        """
        Handle request failures gracefully.

        Args:
            failure: Twisted failure object
        """
        story_id = failure.request.meta.get("story_id", "unknown")
        logger.error(f"Request failed for story {story_id}: {failure.value}")
