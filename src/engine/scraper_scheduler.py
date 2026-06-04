#!/usr/bin/env python3
"""
SYNAPSE Background Scraper Scheduler
=====================================
Runs periodic scraping tasks without Redis or Celery Beat.
Designed for Replit environment where only one process group is available.

Schedule:
  - HackerNews:  every 30 minutes (no API key needed)
  - GitHub:      every 2 hours    (no API key needed; GITHUB_TOKEN improves rate limit)
  - arXiv:       every 6 hours    (no API key needed)
  - Tweets:      every 1 hour     (Mastodon public API — no key needed)
  - YouTube:     every 3 hours    (yt-dlp — no API key needed)
  - Trends:      every 2 hours    (computed from scraped data)
  - Briefings:   every 24 hours   (AI-generated daily brief for all users)
  - Summaries:   every 1 hour     (AI article summaries via Replit AI)

This script runs in the background from start-backend.sh.
"""

import os
import sys
import time
import logging
import subprocess

# Setup
BACKEND_DIR = "/home/runner/workspace/synapse/backend"
PYTHON = sys.executable

logging.basicConfig(
    level=logging.INFO,
    format="[scraper-scheduler] %(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def run_scraper(sources):
    """Run the management command for the given sources list."""
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.replit")
    env.setdefault("PYTHONPATH", f"{BACKEND_DIR}:/home/runner/workspace/synapse")

    cmd = [
        PYTHON, "manage.py", "run_scrapers",
        "--sources", *sources,
    ]
    log.info("Running: %s", " ".join(cmd[2:]))
    try:
        result = subprocess.run(
            cmd,
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute hard limit per scrape run
        )
        if result.stdout:
            log.info(result.stdout.strip())
        if result.returncode != 0 and result.stderr:
            log.warning("stderr: %s", result.stderr.strip()[:500])
    except subprocess.TimeoutExpired:
        log.warning("Scraper timed out after 5 minutes.")
    except Exception as e:
        log.error("Scraper error: %s", e)


def run_django_task(task_label, code):
    """Run arbitrary Django management code inline."""
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.replit")
    env.setdefault("PYTHONPATH", f"{BACKEND_DIR}:/home/runner/workspace/synapse")

    cmd = [PYTHON, "-c", code]
    log.info("Running task: %s", task_label)
    try:
        result = subprocess.run(
            cmd,
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.stdout:
            log.info("[%s] %s", task_label, result.stdout.strip()[:400])
        if result.returncode != 0 and result.stderr:
            log.warning("[%s] err: %s", task_label, result.stderr.strip()[:300])
    except subprocess.TimeoutExpired:
        log.warning("[%s] timed out.", task_label)
    except Exception as e:
        log.error("[%s] error: %s", task_label, e)


COMPUTE_TRENDS_CODE = """
import django, os, sys
sys.path.insert(0, '/home/runner/workspace/synapse/backend')
sys.path.insert(0, '/home/runner/workspace/synapse')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.replit'
django.setup()
from apps.trends.tasks import analyze_trends_task
result = analyze_trends_task()
print('Trends:', result)
"""

GENERATE_BRIEFINGS_CODE = """
import django, os, sys
sys.path.insert(0, '/home/runner/workspace/synapse/backend')
sys.path.insert(0, '/home/runner/workspace/synapse')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.replit'
django.setup()
from apps.users.models import User
from apps.core.tasks import generate_user_briefing
users = list(User.objects.filter(is_active=True).values_list('id', flat=True))
print(f'Generating briefings for {len(users)} users...')
for uid in users:
    try:
        result = generate_user_briefing(str(uid))
        print(f'  user={uid} status={result.get(\"status\")} len={result.get(\"content_length\",0)}')
    except Exception as e:
        print(f'  user={uid} error={e}')
"""

SUMMARIZE_ARTICLES_CODE = """
import django, os, sys
sys.path.insert(0, '/home/runner/workspace/synapse/backend')
sys.path.insert(0, '/home/runner/workspace/synapse')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.replit'
django.setup()
from apps.articles.tasks import summarize_pending_articles
result = summarize_pending_articles(batch_size=30)
print('Summarize result:', result)
"""

SCRAPE_TWEETS_CODE = """
import django, os, sys
sys.path.insert(0, '/home/runner/workspace/synapse/backend')
sys.path.insert(0, '/home/runner/workspace/synapse')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.replit'
django.setup()
from apps.core.tasks import scrape_twitter
# Scrape multiple AI/tech topics from Mastodon
topics = ['AI', 'machinelearning', 'python', 'rust', 'typescript', 'llm', 'opensource']
total = 0
for topic in topics:
    try:
        r = scrape_twitter(max_results=20, query=topic, use_nitter=False)
        saved = r.get('saved', 0) if isinstance(r, dict) else 0
        total += saved
        print(f'  topic={topic} saved={saved}')
    except Exception as e:
        print(f'  topic={topic} error={e}')
print(f'Tweet scrape done. Total saved: {total}')
"""

SCRAPE_YOUTUBE_CODE = """
import django, os, sys
sys.path.insert(0, '/home/runner/workspace/synapse/backend')
sys.path.insert(0, '/home/runner/workspace/synapse')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.replit'
django.setup()
from apps.core.tasks import scrape_youtube
result = scrape_youtube(max_per_query=15, queries=20)
print('YouTube result:', result)
"""


def main():
    log.info("Scraper scheduler starting. Waiting 30s for Django to start up...")
    time.sleep(30)  # Give Daphne time to start first

    # Track last run times (epoch seconds)
    last_hn = 0
    last_github = 0
    last_arxiv = 0
    last_tweets = 0
    last_youtube = 0
    last_trends = 0
    last_briefings = 0
    last_summaries = 0

    INTERVAL_HN        = 30 * 60        # 30 minutes
    INTERVAL_GITHUB    = 2 * 3600       # 2 hours
    INTERVAL_ARXIV     = 6 * 3600       # 6 hours
    INTERVAL_TWEETS    = 1 * 3600       # 1 hour
    INTERVAL_YOUTUBE   = 3 * 3600       # 3 hours
    INTERVAL_TRENDS    = 2 * 3600       # 2 hours (after github+hn have run)
    INTERVAL_BRIEFINGS = 24 * 3600      # 24 hours (once per day)
    INTERVAL_SUMMARIES = 1 * 3600       # 1 hour

    log.info("Starting scraper schedule loop.")

    while True:
        now = time.time()

        if now - last_hn >= INTERVAL_HN:
            log.info("Running HackerNews scraper...")
            run_scraper(["hn"])
            last_hn = time.time()

        if now - last_github >= INTERVAL_GITHUB:
            log.info("Running GitHub scraper...")
            run_scraper(["github"])
            last_github = time.time()

        if now - last_arxiv >= INTERVAL_ARXIV:
            log.info("Running arXiv scraper...")
            run_scraper(["arxiv"])
            last_arxiv = time.time()

        if now - last_tweets >= INTERVAL_TWEETS:
            log.info("Running Mastodon tweet scraper...")
            run_django_task("tweets", SCRAPE_TWEETS_CODE)
            last_tweets = time.time()

        if now - last_youtube >= INTERVAL_YOUTUBE:
            log.info("Running YouTube scraper...")
            run_django_task("youtube", SCRAPE_YOUTUBE_CODE)
            last_youtube = time.time()

        if now - last_trends >= INTERVAL_TRENDS:
            log.info("Computing trends from scraped data...")
            run_django_task("trends", COMPUTE_TRENDS_CODE)
            last_trends = time.time()

        if now - last_summaries >= INTERVAL_SUMMARIES:
            log.info("Summarizing pending articles (AI)...")
            run_django_task("summaries", SUMMARIZE_ARTICLES_CODE)
            last_summaries = time.time()

        if now - last_briefings >= INTERVAL_BRIEFINGS:
            log.info("Generating daily briefings for all users...")
            run_django_task("briefings", GENERATE_BRIEFINGS_CODE)
            last_briefings = time.time()

        # Sleep 60 seconds between schedule checks
        time.sleep(60)


if __name__ == "__main__":
    main()
