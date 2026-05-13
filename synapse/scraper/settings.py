# ── SYNAPSE Scrapy Settings ──────────────────────────────────
import os
import sys
from pathlib import Path

# Add backend to path so Django models are accessible
BASE_DIR = Path(__file__).resolve().parent.parent
# Local dev: /project/scraper/settings.py -> /project/backend
# Docker:    /app/scraper/settings.py -> /app (no backend/ subdir)
_backend_dir = BASE_DIR / "backend"
sys.path.insert(0, str(_backend_dir if _backend_dir.exists() else BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE",
    "config.settings.development" if _backend_dir.exists() else "config.settings.production")

BOT_NAME = "synapse_scraper"
SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"

# ── Politeness ───────────────────────────────────────────────
ROBOTSTXT_OBEY = True
DOWNLOAD_DELAY = 1.5
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 2
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# ── User Agent Rotation ──────────────────────────────────────
USER_AGENT = "SYNAPSE-Bot/1.0 (+https://github.com/HayreKhan750/SYNAPSE)"
DOWNLOADER_MIDDLEWARES = {
    "scraper.middlewares.rotate_useragent.RotateUserAgentMiddleware": 400,
    "scraper.middlewares.retry.CustomRetryMiddleware": 550,
    "scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware": 810,
}

# ── Item Pipelines ───────────────────────────────────────────
ITEM_PIPELINES = {
    "scraper.pipelines.validate.ValidationPipeline": 100,
    "scraper.pipelines.deduplicate.DeduplicationPipeline": 200,
    "scraper.pipelines.database.DatabasePipeline": 300,
}

# ── Retry ────────────────────────────────────────────────────
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 429]
RETRY_BACKOFF = True
RETRY_BACKOFF_MAX = 60

# ── Cache (for development) ──────────────────────────────────
HTTPCACHE_ENABLED = False  # Enable during dev to avoid repeated requests

# ── Redis connection (for deduplication) ─────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6380/0")

# ── Feed exports ─────────────────────────────────────────────
FEED_EXPORT_ENCODING = "utf-8"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
LOG_LEVEL = "INFO"
