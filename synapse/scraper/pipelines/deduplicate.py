"""
Deduplication Pipeline for SYNAPSE
Uses Redis to track and eliminate duplicate items across scraping runs.
Gracefully degrades if Redis is unavailable.

Architecture: Global deduplication keys. When a user_id is present and an
item is a duplicate, the item is PASSED THROUGH (marked as _is_existing)
so that the DatabasePipeline can still create the user ↔ item junction row.
Only truly anonymous duplicates are dropped.
"""

import hashlib
import logging
import os

import redis
from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)


class DeduplicationPipeline:
    """
    Deduplicates items using Redis key-value store.

    - ArticleItem: deduplicates on SHA-256 hash of URL
    - RepositoryItem: deduplicates on github_id
    - ResearchPaperItem: deduplicates on arxiv_id
    - VideoItem: deduplicates on youtube_id

    When a user_id context exists, duplicates are passed through so the
    DB pipeline can create the junction link. When there is no user context,
    true duplicates are dropped.
    """

    # Redis key prefixes for different item types (global scope)
    REDIS_KEYS = {
        "ArticleItem": "synapse:seen_urls",
        "RepositoryItem": "synapse:seen_github_ids",
        "ResearchPaperItem": "synapse:seen_arxiv_ids",
        "VideoItem": "synapse:seen_youtube_ids",
        "TweetItem": "synapse:seen_tweet_ids",
    }

    # Field to deduplicate on for each item type
    DEDUP_FIELDS = {
        "ArticleItem": "url",
        "RepositoryItem": "github_id",
        "ResearchPaperItem": "arxiv_id",
        "VideoItem": "youtube_id",
        "TweetItem": "tweet_id",
    }

    def __init__(self):
        """Initialize the pipeline."""
        self.redis_client = None
        self.redis_available = False

    def open_spider(self, spider):
        """
        Initialize Redis connection when spider opens.

        Args:
            spider: Spider instance
        """
        try:
            # Get Redis URL from Scrapy settings
            redis_url = spider.settings.get("REDIS_URL", "redis://localhost:6379/0")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            self.redis_available = True
            logger.info(f"Connected to Redis at {redis_url}")
        except Exception as e:
            self.redis_available = False
            logger.warning(
                f"Failed to connect to Redis: {e}. "
                "Deduplication disabled - will process all items."
            )

    def close_spider(self, spider):
        """
        Clean up Redis connection when spider closes.

        Args:
            spider: Spider instance
        """
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Closed Redis connection")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

    def process_item(self, item, spider):
        """
        Process an item, checking for duplicates.

        If the item is a duplicate BUT the spider has a user_id, the item
        is passed through (marked _is_existing=True) so the DB pipeline
        can still create the user junction row.

        Args:
            item: Scrapy item to check
            spider: Spider instance

        Returns:
            item: Passed through if unique or if user needs linking

        Raises:
            DropItem: If item is a duplicate AND no user context exists
        """
        if not self.redis_available:
            # Redis unavailable - pass through
            return item

        item_type = item.__class__.__name__
        redis_key = self.REDIS_KEYS.get(item_type)
        dedup_field = self.DEDUP_FIELDS.get(item_type)

        if not redis_key or not dedup_field:
            # Unknown item type - pass through
            return item

        if dedup_field not in item:
            logger.warning(f"Missing dedup field '{dedup_field}' in {item_type}")
            return item

        # Get the value to deduplicate on
        dedup_value = item[dedup_field]

        # For URLs, hash them; for IDs, use as-is
        if dedup_field == "url":
            dedup_key = hashlib.sha256(dedup_value.encode()).hexdigest()
        else:
            dedup_key = str(dedup_value)

        # Check if there is a user context for this scraping run
        user_id = getattr(spider, "user_id", None) or os.environ.get("SYNAPSE_USER_ID")

        try:
            # Check if we've seen this before
            if self.redis_client.sismember(redis_key, dedup_key):
                if user_id:
                    # Duplicate EXISTS but user needs linking → pass through
                    item["_is_existing"] = True
                    logger.debug(
                        f"Existing {item_type} ({dedup_field}={dedup_value}) "
                        f"— passing through for user {user_id} junction link"
                    )
                    return item
                else:
                    # No user context — true duplicate, drop it
                    raise DropItem(
                        f"Duplicate {item_type} ({dedup_field}={dedup_value}) "
                        f"from {spider.name}"
                    )

            # Add to seen set and refresh TTL (24h) so items re-appear the next day
            self.redis_client.sadd(redis_key, dedup_key)
            self.redis_client.expire(redis_key, 24 * 60 * 60)
            logger.debug(f"New {item_type} ({dedup_field}={dedup_value})")
            return item

        except redis.RedisError as e:
            logger.error(f"Redis error during deduplication: {e}")
            # Degrade gracefully - pass item through
            return item
