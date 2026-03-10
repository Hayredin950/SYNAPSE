"""
Management command — reset_failed_summaries

When the LLM provider for article summarization is unavailable (bad / missing
API key, rate-limit, network error, etc.), the summarize_article task writes
the sentinel value SUMMARY_FAILED_SENTINEL to Article.summary so the task
isn't re-queued forever in a tight loop.

Once the operator fixes the underlying issue (e.g. configures GROQ_API_KEY or
AI_GATEWAY_API_KEY), the previously-failed articles will stay stuck because
summarize_pending_articles excludes the sentinel. This command clears those
sentinels and (optionally) re-queues the affected articles.

Usage:
    python manage.py reset_failed_summaries           # dry-run, prints count
    python manage.py reset_failed_summaries --apply   # clear sentinels
    python manage.py reset_failed_summaries --apply --requeue  # also re-queue
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Clear __failed__ summary sentinels so articles can be re-summarized "
        "by a now-healthy LLM provider."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually clear the sentinels (otherwise dry-run).",
        )
        parser.add_argument(
            "--requeue",
            action="store_true",
            help="After clearing, immediately enqueue summarize_pending_articles.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Batch size for the optional re-queue (default: 50).",
        )

    def handle(self, *args, **options):
        from apps.articles.models import Article
        from apps.articles.tasks import (
            SUMMARY_FAILED_SENTINEL,
            summarize_pending_articles,
        )

        qs = Article.objects.filter(summary=SUMMARY_FAILED_SENTINEL)
        count = qs.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No failed-summary sentinels found."))
            return

        if not options["apply"]:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY-RUN: {count} article(s) carry the failure sentinel. "
                    "Re-run with --apply to clear them."
                )
            )
            return

        updated = qs.update(summary="")
        self.stdout.write(
            self.style.SUCCESS(f"Cleared {updated} failure sentinel(s).")
        )

        if options["requeue"]:
            batch = options["batch_size"]
            task = summarize_pending_articles.apply_async(args=[batch], queue="nlp")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Re-queued summarize_pending_articles "
                    f"(batch_size={batch}, task_id={task.id})."
                )
            )
