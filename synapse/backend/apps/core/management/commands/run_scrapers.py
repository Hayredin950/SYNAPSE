"""
Management command: run_scrapers

Triggers all configured scrapers immediately (no Celery Beat / Redis needed).
HackerNews and GitHub scrapers work without any API keys.
arXiv scraper also requires no key.

Usage:
  python manage.py run_scrapers
  python manage.py run_scrapers --sources hn github
"""

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run all scrapers immediately to populate real scraped data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sources",
            nargs="+",
            default=["hn", "github", "arxiv"],
            choices=["hn", "github", "arxiv", "youtube", "twitter"],
            help="Which scrapers to run (default: hn github arxiv)",
        )

    def handle(self, *args, **options):
        sources = options["sources"]
        self.stdout.write(f"Running scrapers: {sources}")

        from apps.core.tasks import (
            scrape_hackernews,
            scrape_github,
            scrape_arxiv,
        )

        if "hn" in sources:
            self.stdout.write("  → HackerNews (top 100)...")
            try:
                result = scrape_hackernews("top", 100)
                self.stdout.write(self.style.SUCCESS(f"     HN: {result}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"     HN failed: {e}"))

        if "github" in sources:
            self.stdout.write("  → GitHub trending (7 days)...")
            try:
                result = scrape_github(7, None, 100)
                self.stdout.write(self.style.SUCCESS(f"     GitHub: {result}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"     GitHub failed: {e}"))

        if "arxiv" in sources:
            self.stdout.write("  → arXiv papers...")
            try:
                result = scrape_arxiv(None, 7, 50)
                self.stdout.write(self.style.SUCCESS(f"     arXiv: {result}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"     arXiv failed: {e}"))

        if "youtube" in sources:
            self.stdout.write("  → YouTube videos...")
            try:
                from apps.core.tasks import scrape_youtube
                result = scrape_youtube(30, 20)
                self.stdout.write(self.style.SUCCESS(f"     YouTube: {result}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"     YouTube failed (needs API key): {e}"))

        if "twitter" in sources:
            self.stdout.write("  → Twitter/X...")
            try:
                from apps.core.tasks import scrape_twitter
                result = scrape_twitter(max_results=30, query="AI machine learning LLM", use_nitter=False)
                self.stdout.write(self.style.SUCCESS(f"     Twitter: {result}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"     Twitter failed (needs bearer token): {e}"))

        self.stdout.write(self.style.SUCCESS("All scrapers done."))
