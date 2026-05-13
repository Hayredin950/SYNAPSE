"""
Nitter Spider for SYNAPSE
Scrapes tweets from public Nitter instances (no X API key required).

Nitter is an open-source, privacy-respecting X/Twitter frontend.
Public instances mirror tweet data without requiring authentication.

Usage:
    scrapy crawl nitter -a query="AI machine learning" -a max_results=50
    scrapy crawl nitter -a username="karpathy" -a max_results=30
"""

import logging
import random
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import scrapy

from scraper.items import TweetItem

logger = logging.getLogger(__name__)

NITTER_INSTANCES = [
    "https://nitter.tiekoetter.com",  # Primary — verified working
    "https://nitter.it",
    "https://nitter.poast.org",
    "https://nt.nani.wtf",
    "https://nitter.rawbit.ninja",
]

TECH_ACCOUNTS = [
    "sama",
    "karpathy",
    "ylecun",
    "darioamodei",
    "demishassabis",
    "ilyasut",
    "fchollet",
    "mmitchell_ai",
    "goodfellow_ian",
    "hardmaru",
    "emostaque",
    "danielnouri",
    "srush_nlp",
    "rasbt",
    "jeremyphoward",
    "iximiuz",
    "gdb",
    "tferriss",
    "naval",
    "balajis",
]

DEFAULT_QUERIES = [
    "AI machine learning LLM",
    "Python programming software",
    "web development React TypeScript",
    "cybersecurity hacking security",
    "cloud computing DevOps Kubernetes",
    "open source GitHub",
    "research paper arxiv",
]

HASHTAG_TOPICS = {
    (
        "ai",
        "machinelearning",
        "llm",
        "deeplearning",
        "gpt",
        "chatgpt",
        "genai",
        "neural",
        "transformer",
        "openai",
        "anthropic",
        "gemini",
        "claude",
    ): "AI",
    (
        "webdev",
        "javascript",
        "typescript",
        "reactjs",
        "nextjs",
        "frontend",
        "css",
        "html",
        "svelte",
        "vue",
        "angular",
    ): "Web Dev",
    (
        "cybersecurity",
        "infosec",
        "hacking",
        "malware",
        "ransomware",
        "privacy",
        "encryption",
        "vulnerability",
        "exploit",
    ): "Security",
    (
        "cloudcomputing",
        "aws",
        "azure",
        "gcp",
        "devops",
        "kubernetes",
        "docker",
        "terraform",
        "serverless",
        "microservices",
    ): "Cloud",
    (
        "research",
        "paper",
        "arxiv",
        "datascience",
        "statistics",
        "experiment",
        "dataset",
        "benchmark",
    ): "Research",
    (
        "python",
        "rustlang",
        "golang",
        "java",
        "programming",
        "coding",
        "opensource",
        "github",
        "algorithm",
    ): "Programming",
    (
        "bitcoin",
        "ethereum",
        "crypto",
        "blockchain",
        "defi",
        "nft",
        "web3",
        "solana",
    ): "Crypto",
}


def _infer_topic(hashtags, text):
    """Infer topic from hashtags and tweet text."""
    combined = " ".join(hashtags).lower() + " " + text.lower()
    for keywords, topic in HASHTAG_TOPICS.items():
        if any(kw in combined for kw in keywords):
            return topic
    return "AI"  # default


def _parse_count(text):
    """Parse tweet stat count like '1.2K', '3M', '42' → int."""
    if not text:
        return 0
    text = text.strip().replace(",", "")
    try:
        if text.endswith("K"):
            return int(float(text[:-1]) * 1000)
        if text.endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        return int(text)
    except (ValueError, AttributeError):
        return 0


def _parse_date(date_str):
    """Parse Nitter date strings to ISO format."""
    if not date_str:
        return None
    # Normalise: strip leading/trailing whitespace, remove 'UTC'/'·' separators
    s = date_str.strip().replace("UTC", "").replace("·", " ").strip()
    # Collapse multiple spaces left by removals
    s = re.sub(r"\s+", " ", s)
    for fmt in (
        "%b %d, %Y %I:%M %p",  # Dec 25, 2024 3:30 PM
        "%b %d, %Y, %I:%M %p",  # Dec 25, 2024, 3:30 PM
        "%d %b %Y %I:%M %p",  # 25 Dec 2024 3:30 PM
        "%Y-%m-%d %H:%M:%S",  # 2024-12-25 15:30:00
        "%b %d %Y %I:%M %p",  # Dec 25 2024 3:30 PM
        "%I:%M %p · %b %d, %Y",  # 3:30 PM · Dec 25, 2024
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    logger.debug(f"Could not parse Nitter date: {date_str!r}")
    return None


class NitterSpider(scrapy.Spider):
    """
    Spider that scrapes tweets via public Nitter instances.
    Falls back gracefully if an instance is down.
    No API key required.
    """

    name = "nitter"

    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 1,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "DOWNLOADER_MIDDLEWARES": {
            "scraper.middlewares.retry.CustomRetryMiddleware": 550,
        },
    }

    def __init__(
        self, query=None, queries=None, username=None, max_results=50, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)
        self.items_scraped = 0
        self.instances = list(NITTER_INSTANCES)  # Primary instance first, no shuffle
        self.current_instance_idx = 0

        if username:
            self.mode = "profile"
            self.usernames = [username]
            self.queries = []
        elif queries:
            import json

            self.mode = "search"
            self.queries = (
                json.loads(queries) if isinstance(queries, str) else list(queries)
            )
            self.usernames = []
        elif query:
            self.mode = "search"
            self.queries = [query]
            self.usernames = []
        else:
            self.mode = "search"
            self.queries = DEFAULT_QUERIES
            self.usernames = []

        # Store user_id for personalization
        self.user_id = kwargs.get("user_id")

    def start_requests(self):
        """Generate initial requests."""
        instance = self.instances[self.current_instance_idx]

        if self.mode == "profile":
            for username in self.usernames:
                url = f"{instance}/{username}"
                yield scrapy.Request(
                    url,
                    callback=self.parse_profile,
                    errback=self.handle_error,
                    meta={"username": username, "nitter_instance": instance},
                )
        else:
            for query in self.queries:
                url = f"{instance}/search?q={quote_plus(query)}&f=tweets"
                yield scrapy.Request(
                    url,
                    callback=self.parse_search,
                    errback=self.handle_error,
                    meta={"query": query, "nitter_instance": instance},
                )

    def handle_error(self, failure):
        """Try next Nitter instance on failure."""
        self.current_instance_idx = (self.current_instance_idx + 1) % len(
            self.instances
        )
        instance = self.instances[self.current_instance_idx]
        meta = failure.request.meta

        if "query" in meta:
            url = f'{instance}/search?q={quote_plus(meta["query"])}&f=tweets'
            yield scrapy.Request(
                url,
                callback=self.parse_search,
                errback=self.handle_error,
                meta={**meta, "nitter_instance": instance},
            )
        elif "username" in meta:
            url = f'{instance}/{meta["username"]}'
            yield scrapy.Request(
                url,
                callback=self.parse_profile,
                errback=self.handle_error,
                meta={**meta, "nitter_instance": instance},
            )

    def parse_search(self, response):
        """Parse Nitter search results page."""
        instance = response.meta.get("nitter_instance", self.instances[0])

        if response.status != 200:
            logger.warning(
                f"Nitter search returned {response.status}, trying next instance"
            )
            self.current_instance_idx = (self.current_instance_idx + 1) % len(
                self.instances
            )
            instance = self.instances[self.current_instance_idx]
            url = f'{instance}/search?q={quote_plus(response.meta["query"])}&f=tweets'
            yield scrapy.Request(
                url,
                callback=self.parse_search,
                errback=self.handle_error,
                meta={**response.meta, "nitter_instance": instance},
            )
            return

        yield from self._extract_tweets(response, query=response.meta.get("query"))

        # Pagination
        next_href = response.css("div.show-more a::attr(href)").get()
        if next_href and self.items_scraped < self.max_results:
            next_url = instance + next_href
            yield scrapy.Request(
                next_url,
                callback=self.parse_search,
                errback=self.handle_error,
                meta=response.meta,
            )

    def parse_profile(self, response):
        """Parse a Nitter user profile/timeline page."""
        instance = response.meta.get("nitter_instance", self.instances[0])

        if response.status != 200:
            logger.warning(
                f"Nitter profile returned {response.status}, trying next instance"
            )
            self.current_instance_idx = (self.current_instance_idx + 1) % len(
                self.instances
            )
            instance = self.instances[self.current_instance_idx]
            url = f'{instance}/{response.meta["username"]}'
            yield scrapy.Request(
                url,
                callback=self.parse_profile,
                errback=self.handle_error,
                meta={**response.meta, "nitter_instance": instance},
            )
            return

        yield from self._extract_tweets(response)

    def _extract_tweets(self, response, query=None):
        """Extract tweet items from a Nitter page."""
        for tweet_el in response.css("div.timeline-item"):
            if self.items_scraped >= self.max_results:
                return
            # Skip pinned and promoted
            if tweet_el.css("div.pinned") or tweet_el.css("div.promoted"):
                continue
            item = self._parse_tweet(
                tweet_el, response.meta.get("nitter_instance", ""), query
            )
            if item:
                self.items_scraped += 1
                yield item

    def _parse_tweet(self, el, instance, query=None):
        """Extract structured data from a single tweet container."""
        # Text
        text = " ".join(el.css("div.tweet-content *::text").getall()).strip()
        if not text:
            return None

        # Tweet URL / ID
        tweet_link = el.css("a.tweet-link::attr(href)").get("")
        tweet_id = ""
        if "/status/" in tweet_link:
            tweet_id = tweet_link.split("/status/")[-1].split("#")[0].strip("/")

        # Author
        author_username = (
            el.css("a.username::text")
            .get(el.css(".tweet-name-row a::attr(href)").get("unknown"))
            .lstrip("@")
            .strip()
        )
        author_display_name = (
            el.css("a.fullname::text")
            .get(el.css(".tweet-name-row a.fullname::text").get(""))
            .strip()
        )
        author_verified = bool(el.css(".icon-ok"))
        author_profile_image = el.css("img.tweet-avatar::attr(src)").get(
            el.css("img.avatar::attr(src)").get("")
        )
        if author_profile_image and not author_profile_image.startswith("http"):
            author_profile_image = instance + author_profile_image

        # Date
        date_str = el.css("span.tweet-date a::attr(title)").get("")
        posted_at = _parse_date(date_str)

        # Stats
        stats = {}
        for stat_el in el.css("div.tweet-stats div.tweet-stat"):
            icon_class = stat_el.css("span[class^='icon']::attr(class)").get("")
            count_text = stat_el.css("span:last-child::text").get("0")
            count = _parse_count(count_text)
            if "heart" in icon_class:
                stats["like_count"] = count
            elif "retweet" in icon_class:
                stats["retweet_count"] = count
            elif "comment" in icon_class:
                stats["reply_count"] = count
            elif "quote" in icon_class:
                stats["quote_count"] = count

        # Hashtags & mentions
        hashtags = [h.lstrip("#") for h in el.css("a.hashtag::text").getall()]
        mentions = [m.lstrip("@") for m in el.css("a.mention::text").getall()]

        # Media
        media_urls = []
        for img_src in el.css("div.attachments img::attr(src)").getall():
            if not img_src.startswith("http"):
                img_src = instance + img_src
            media_urls.append(img_src)

        # Tweet URL
        tweet_url = (
            f"https://x.com/{author_username}/status/{tweet_id}" if tweet_id else ""
        )

        # Flags
        is_retweet = bool(text.startswith("RT @"))
        is_reply = bool(el.css("div.reply-indicator"))
        is_quote = bool(el.css("div.quote"))

        # Topic
        topic = _infer_topic(hashtags, text)

        return TweetItem(
            tweet_id=tweet_id,
            text=text,
            author_username=author_username,
            author_display_name=author_display_name,
            author_profile_image=author_profile_image,
            author_verified=author_verified,
            author_followers=0,
            like_count=stats.get("like_count", 0),
            retweet_count=stats.get("retweet_count", 0),
            reply_count=stats.get("reply_count", 0),
            quote_count=stats.get("quote_count", 0),
            view_count=0,
            bookmark_count=0,
            posted_at=posted_at,
            hashtags=hashtags,
            mentions=mentions,
            media_urls=media_urls,
            urls=[],
            is_retweet=is_retweet,
            is_reply=is_reply,
            is_quote=is_quote,
            conversation_id=tweet_id,
            in_reply_to_user=None,
            lang="en",
            url=tweet_url,
            source_label="nitter",
            topic=topic,
            trending_score=0.0,
            metadata={
                "scraped_via": "nitter",
                "nitter_instance": instance,
                "query": query,
            },
        )
