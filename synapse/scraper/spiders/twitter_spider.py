"""
X (Twitter) Spider for SYNAPSE
Scrapes tweets using the X/Twitter API v2 (Recent Search).
Searches for tech-focused tweets by topic queries, hashtags, and trending tech accounts.
Respects X API rate limits (450 requests/15-min window for App-only auth).
"""

import logging
import os
import re
from datetime import datetime, timedelta, timezone

import scrapy

logger = logging.getLogger(__name__)


class XTwitterSpider(scrapy.Spider):
    """
    Spider for scraping tweets from the X (Twitter) API v2.

    Usage:
        scrapy crawl twitter -a query="AI OR machine learning" -a max_results=100
        scrapy crawl twitter -a queries='["python","javascript","rust"]' -a max_results=50
    """

    name = "twitter"
    allowed_domains = ["api.twitter.com", "api.x.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 1,
    }

    DEFAULT_QUERIES = [
        "#AI OR #MachineLearning OR #LLM",
        "#WebDev OR #ReactJS OR #TypeScript",
        "#Python OR #RustLang OR #Golang",
        "#CyberSecurity OR #InfoSec",
        "#CloudComputing OR #DevOps OR #Kubernetes",
    ]

    def __init__(self, query=None, queries=None, max_results=100, *args, **kwargs):
        super(XTwitterSpider, self).__init__(*args, **kwargs)
        self.max_results = int(max_results)
        self.items_scraped = 0

        if queries:
            import json

            self.queries = json.loads(queries) if isinstance(queries, str) else queries
        elif query:
            self.queries = [query]
        else:
            self.queries = self.DEFAULT_QUERIES

        self.bearer_token = os.environ.get("X_API_KEY") or os.environ.get(
            "TWITTER_BEARER_TOKEN"
        )

        # Store user_id for personalization
        self.user_id = kwargs.get("user_id")
        if not self.bearer_token:
            logger.warning(
                "X_API_KEY / TWITTER_BEARER_TOKEN not set. "
                "Set one in your .env file to authenticate with the X API v2."
            )

    def start_requests(self):
        """Generate initial requests for each query."""
        for query_str in self.queries:
            if self.items_scraped >= self.max_results:
                break
            url = self._build_search_url(query_str)
            logger.info(f"Starting X search: {query_str}")
            yield scrapy.Request(
                url,
                callback=self.parse,
                headers=self._headers(),
                errback=self.handle_error,
                meta={"query": query_str},
            )

    def parse(self, response):
        """Parse X API v2 search results."""
        if response.status == 429:
            reset_ts = int(response.headers.get("x-rate-limit-reset", 0))
            wait = (
                max(reset_ts - int(datetime.now(timezone.utc).timestamp()), 60)
                if reset_ts
                else 900
            )
            logger.warning(f"X API rate limited. Reset in {wait}s. Stopping spider.")
            self.crawler.engine.close_spider(self, "rate_limit_exceeded")
            return

        if response.status != 200:
            logger.error(f"X API returned {response.status}: {response.text[:500]}")
            return

        try:
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return

        tweets = data.get("data", [])
        includes = data.get("includes", {})
        users_by_id = {u["id"]: u for u in includes.get("users", [])}
        media_by_key = {m["media_key"]: m for m in includes.get("media", [])}

        logger.info(f"Processing {len(tweets)} tweets from X search")

        for tweet_data in tweets:
            if self.items_scraped >= self.max_results:
                logger.info(f"Reached item limit ({self.max_results}). Stopping.")
                return

            item = self._make_tweet_item(tweet_data, users_by_id, media_by_key)
            self.items_scraped += 1
            yield item

        # Pagination via next_token
        next_token = data.get("meta", {}).get("next_token")
        if next_token and self.items_scraped < self.max_results:
            query_str = response.meta.get("query", "")
            url = self._build_search_url(query_str, next_token)
            yield scrapy.Request(
                url,
                callback=self.parse,
                headers=self._headers(),
                errback=self.handle_error,
                meta=response.meta,
            )

    def _make_tweet_item(self, tweet_data, users_by_id, media_by_key):
        """Build a TweetItem from X API v2 response."""
        from scraper.items import TweetItem

        item = TweetItem()
        author_id = tweet_data.get("author_id", "")
        author = users_by_id.get(author_id, {})

        item["tweet_id"] = tweet_data.get("id")
        item["text"] = tweet_data.get("text", "")
        item["author_username"] = author.get("username", "")
        item["author_display_name"] = author.get("name", "")
        item["author_profile_image"] = author.get("profile_image_url", "")
        item["author_verified"] = author.get("verified", False)
        item["author_followers"] = author.get("public_metrics", {}).get(
            "followers_count", 0
        )
        item["posted_at"] = tweet_data.get("created_at")

        # Public metrics
        metrics = tweet_data.get("public_metrics", {})
        item["retweet_count"] = metrics.get("retweet_count", 0)
        item["like_count"] = metrics.get("like_count", 0)
        item["reply_count"] = metrics.get("reply_count", 0)
        item["quote_count"] = metrics.get("quote_count", 0)
        item["view_count"] = metrics.get("impression_count", 0)
        item["bookmark_count"] = metrics.get("bookmark_count", 0)

        # Extract entities
        text = tweet_data.get("text", "")
        item["hashtags"] = [f"#{t}" for t in re.findall(r"#(\w+)", text)]
        item["mentions"] = [f"@{m}" for m in re.findall(r"@(\w+)", text)]

        # URLs
        urls_field = tweet_data.get("urls", []) or []
        item["urls"] = [u.get("expanded_url", u.get("url", "")) for u in urls_field]

        # Media
        media_keys = (
            tweet_data.get("attachments", {}).get("media_keys", [])
            if tweet_data.get("attachments")
            else []
        )
        item["media_urls"] = []
        for mk in media_keys:
            m = media_by_key.get(mk, {})
            url = m.get("url") or m.get("preview_image_url", "")
            if url:
                item["media_urls"].append(url)

        # Type indicators
        item["is_retweet"] = text.startswith("RT @")
        item["is_reply"] = bool(tweet_data.get("in_reply_to_user_id"))
        item["is_quote"] = tweet_data.get("referenced_tweets", []) and any(
            r.get("type") == "quoted" for r in tweet_data.get("referenced_tweets", [])
        )
        item["conversation_id"] = tweet_data.get("conversation_id", "")

        # Reply context
        reply_user_id = tweet_data.get("in_reply_to_user_id", "")
        item["in_reply_to_user"] = (
            users_by_id.get(reply_user_id, {}).get("username", "")
            if reply_user_id
            else ""
        )

        item["lang"] = tweet_data.get("lang", "")
        item["source_label"] = tweet_data.get("source", "")

        # Build URL
        username = item["author_username"]
        tweet_id = item["tweet_id"]
        item["url"] = (
            f"https://x.com/{username}/status/{tweet_id}"
            if username and tweet_id
            else ""
        )

        # Calculate trending score (engagement-weighted)
        item["trending_score"] = (
            metrics.get("like_count", 0) * 1.0
            + metrics.get("retweet_count", 0) * 2.0
            + metrics.get("reply_count", 0) * 1.5
            + metrics.get("quote_count", 0) * 3.0
            + metrics.get("bookmark_count", 0) * 2.5
        )

        # Inferred topic from hashtags/query context
        item["topic"] = self._infer_topic(text, item["hashtags"])

        item["metadata"] = {
            "query": tweet_data.get("query", ""),
            "edit_history_tweet_ids": tweet_data.get("edit_history_tweet_ids", []),
            "context_annotations": tweet_data.get("context_annotations", []),
            "entities": tweet_data.get("entities", {}),
            "possibly_sensitive": tweet_data.get("possibly_sensitive", False),
            "reply_settings": tweet_data.get("reply_settings", ""),
        }

        return item

    def _infer_topic(self, text, hashtags):
        """Infer topic from tweet text and hashtags."""
        text_lower = text.lower()
        hashtag_lower = " ".join(h.lower() for h in hashtags)

        topic_map = {
            "AI": [
                "#ai",
                "#machinelearning",
                "#llm",
                "#deeplearning",
                "artificial intelligence",
                "gpt",
                "chatgpt",
                "#genai",
            ],
            "Web Dev": [
                "#webdev",
                "#javascript",
                "#typescript",
                "#reactjs",
                "#nextjs",
                "#frontend",
                "#css",
                "#html",
            ],
            "Security": [
                "#cybersecurity",
                "#infosec",
                "#hacking",
                "#malware",
                "#ransomware",
                "#privacy",
            ],
            "Cloud": [
                "#cloudcomputing",
                "#aws",
                "#azure",
                "#gcp",
                "#devops",
                "#kubernetes",
                "#docker",
                "#terraform",
            ],
            "Research": [
                "#research",
                "#science",
                "#paper",
                "#arxiv",
                "#datascience",
                "#statistics",
            ],
            "Programming": [
                "#python",
                "#rustlang",
                "#golang",
                "#java",
                "#programming",
                "#coding",
                "#opensource",
            ],
        }

        combined = text_lower + " " + hashtag_lower
        for topic, keywords in topic_map.items():
            if any(kw in combined for kw in keywords):
                return topic

        return "Tech"

    def _build_search_url(self, query, next_token=None):
        """Build X API v2 recent search URL."""
        from urllib.parse import urlencode

        params = {
            "query": f"({query}) -is:retweet lang:en",
            "max_results": min(100, self.max_results - self.items_scraped),
            "tweet.fields": "created_at,public_metrics,lang,author_id,conversation_id,in_reply_to_user_id,entities,attachments,referenced_tweets,source,context_annotations,possibly_sensitive,reply_settings,edit_history_tweet_ids",
            "user.fields": "username,name,profile_image_url,verified,public_metrics",
            "media.fields": "url,preview_image_url,type",
            "expansions": "author_id,attachments.media_keys,referenced_tweets.id",
        }
        if next_token:
            params["next_token"] = next_token

        return f"https://api.twitter.com/2/tweets/search/recent?{urlencode(params)}"

    def _headers(self):
        """Return auth headers for X API v2."""
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "User-Agent": "SYNAPSE-Bot/1.0",
        }

    def handle_error(self, failure):
        """Handle request errors gracefully."""
        logger.error(f"X request failed: {failure.request.url}")
        logger.error(f"Error: {failure.value}")
