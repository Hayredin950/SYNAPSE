"""
Custom retry middleware with exponential backoff for Scrapy.

Extends Scrapy's built-in RetryMiddleware to add exponential backoff
and special handling for rate limiting (429) responses.
"""

import logging

from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

logger = logging.getLogger(__name__)


class CustomRetryMiddleware(RetryMiddleware):
    """
    Custom retry middleware with exponential backoff.

    Extends Scrapy's RetryMiddleware to:
    - Add exponential backoff: delay = 2^retry_count seconds (capped at 60s)
    - Handle 429 (Too Many Requests) with a fixed 60s backoff
    - Log all retry attempts with URL, status code, and retry count
    """

    def __init__(self, settings):
        """Initialize the middleware with settings."""
        super().__init__(settings)

    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware instance from crawler object."""
        return cls(crawler.settings)

    def process_response(self, request, response, spider):
        """
        Process response and handle retries with backoff.

        Implements exponential backoff for most errors and a fixed 60s delay
        for 429 (Too Many Requests) responses.

        Args:
            request: Scrapy Request object
            response: Scrapy Response object
            spider: Scrapy Spider instance

        Returns:
            Request (retried) or Response (passed through)
        """
        if response.status == 429:
            # Rate limited - use fixed 60s backoff
            return self._handle_rate_limit(request, response, spider)

        # Use parent class logic for other status codes
        return super().process_response(request, response, spider)

    def _handle_rate_limit(self, request, response, spider):
        """
        Handle 429 (Too Many Requests) responses with 60s backoff.

        Args:
            request: Scrapy Request object
            response: Scrapy Response object
            spider: Scrapy Spider instance

        Returns:
            Request (retried with 60s delay) or Response (if max retries exceeded)
        """
        retry_times = request.meta.get("retry_times", 0)

        if retry_times >= self.max_retry_times:
            logger.error(
                f"Max retries exceeded for {request.url} (429 Too Many Requests). "
                f"Retries: {retry_times}/{self.max_retry_times}"
            )
            return response

        retry_times += 1
        delay = 60  # Fixed 60 second delay for rate limiting

        logger.warning(
            f"Rate limited (429) on {request.url}. "
            f"Retrying in {delay}s (attempt {retry_times}/{self.max_retry_times})"
        )

        request.meta["retry_times"] = retry_times
        request.dont_obey_robotstxt = True

        # Clone and schedule retry with delay
        retry_request = request.copy()
        retry_request.dont_filter = True

        return self._retry_request(retry_request, delay, spider)

    def _retry_request(self, request, delay, spider):
        """
        Schedule a request for retry with specified delay.

        Args:
            request: Scrapy Request object
            delay: Delay in seconds
            spider: Scrapy Spider instance

        Returns:
            Request with download_delay set
        """
        request.priority = request.priority - self.priority_adjust
        request.meta["download_delay"] = delay
        return request

    def process_response(self, request, response, spider):
        """
        Enhanced process_response with exponential backoff for other errors.

        Args:
            request: Scrapy Request object
            response: Scrapy Response object
            spider: Scrapy Spider instance

        Returns:
            Request (retried) or Response (passed through)
        """
        if response.status == 429:
            return self._handle_rate_limit(request, response, spider)

        if response.status in self.retry_http_codes:
            return self._handle_retry_with_backoff(request, response, spider)

        return response

    def _handle_retry_with_backoff(self, request, response, spider):
        """
        Handle retryable HTTP status codes with exponential backoff.

        Args:
            request: Scrapy Request object
            response: Scrapy Response object
            spider: Scrapy Spider instance

        Returns:
            Request (retried) or Response (if max retries exceeded)
        """
        retry_times = request.meta.get("retry_times", 0)

        if retry_times >= self.max_retry_times:
            logger.error(
                f"Max retries exceeded for {request.url} "
                f"(status: {response.status} {response_status_message(response.status)}). "
                f"Retries: {retry_times}/{self.max_retry_times}"
            )
            return response

        retry_times += 1
        # Exponential backoff: delay = 2^retry_count, capped at 60s
        delay = min(2 ** (retry_times - 1), 60)

        logger.warning(
            f"Retrying {request.url} (status: {response.status} "
            f"{response_status_message(response.status)}). "
            f"Backoff: {delay}s (attempt {retry_times}/{self.max_retry_times})"
        )

        request.meta["retry_times"] = retry_times
        request.dont_obey_robotstxt = True

        retry_request = request.copy()
        retry_request.dont_filter = True
        retry_request.priority = retry_request.priority - self.priority_adjust
        retry_request.meta["download_delay"] = delay

        return retry_request
