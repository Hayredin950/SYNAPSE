"""
Validation Pipeline for SYNAPSE
Validates items before they reach storage, enforcing required fields and format constraints.
"""

import logging

from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)


class ValidationPipeline:
    """
    Validates items against required fields and constraints.

    - Checks required fields per item type
    - Validates URL format (http:// or https://)
    - Truncates oversized fields
    - Drops invalid items with logging
    """

    # Required fields per item type
    REQUIRED_FIELDS = {
        "ArticleItem": ["title", "url"],
        "RepositoryItem": ["github_id", "full_name"],
        "ResearchPaperItem": ["arxiv_id", "title"],
        "VideoItem": ["youtube_id", "title"],
    }

    # Field truncation limits (in characters)
    FIELD_LIMITS = {
        "title": 1000,
        "description": 5000,
        "content": 100000,
    }

    # Fields that should be URLs
    URL_FIELDS = ["url", "clone_url", "pdf_url", "thumbnail_url"]

    def process_item(self, item, spider):
        """
        Process an item through validation pipeline.

        Args:
            item: Scrapy item to validate
            spider: Spider instance

        Returns:
            item: Validated item or raises DropItem

        Raises:
            DropItem: If item fails validation
        """
        item_type = self.__class__._get_item_type(item)

        # Check required fields
        required_fields = self.REQUIRED_FIELDS.get(item_type, [])
        for field in required_fields:
            if field not in item or not item[field]:
                raise DropItem(
                    f"Missing required field '{field}' for {item_type} from {spider.name}"
                )

        # Validate URL fields
        for field in self.URL_FIELDS:
            if field in item and item[field]:
                if not self._is_valid_url(item[field]):
                    raise DropItem(
                        f"Invalid URL in field '{field}': {item[field]} "
                        f"for {item_type} from {spider.name}"
                    )

        # Truncate oversized fields
        for field, limit in self.FIELD_LIMITS.items():
            if field in item and item[field] and len(item[field]) > limit:
                logger.warning(
                    f"Truncating field '{field}' from {len(item[field])} "
                    f"to {limit} chars for {item_type} from {spider.name}"
                )
                item[field] = item[field][:limit]

        logger.debug(f"Validated {item_type} from {spider.name}")
        return item

    @staticmethod
    def _get_item_type(item):
        """
        Get the item type name.

        Args:
            item: Scrapy item

        Returns:
            str: Item class name
        """
        return item.__class__.__name__

    @staticmethod
    def _is_valid_url(url):
        """
        Validate URL format.

        Args:
            url (str): URL to validate

        Returns:
            bool: True if URL starts with http:// or https://
        """
        return isinstance(url, str) and (
            url.startswith("http://") or url.startswith("https://")
        )
