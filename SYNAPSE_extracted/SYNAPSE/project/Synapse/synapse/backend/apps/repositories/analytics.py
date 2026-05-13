"""
TASK-602-B2: GitHub star velocity analytics Celery task.

Daily task that:
 1. Reads star_history (daily snapshots) for each repo.
 2. Computes 7-day and 30-day star deltas + velocity (stars/day).
 3. Classifies repos as rising_star / stable / declining.
 4. Sets is_rising_star flag for repos < 6 months old and >100 stars/week.
 5. Appends today's star count to star_history (rolling 90-day window).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task

logger = logging.getLogger(__name__)

RISING_STAR_THRESHOLD = 50  # stars/week → rising_star class
DECLINING_THRESHOLD = -10  # net stars/week → declining
NEW_REPO_DAYS = 183  # 6 months
IS_RISING_THRESHOLD = 100  # stars/week for is_rising_star flag


@shared_task(bind=True, max_retries=1)
def compute_star_velocity(self) -> dict:
    """
    TASK-602-B2: Compute star velocity for all repositories.
    Schedule: daily at 04:00 UTC via Celery beat.
    """
    from django.utils import timezone as dj_tz

    from .models import Repository

    today = dj_tz.now().date()
    today_str = today.isoformat()
    cutoff_7d = today - timedelta(days=7)
    cutoff_30d = today - timedelta(days=30)
    cutoff_new = today - timedelta(days=NEW_REPO_DAYS)

    repos = Repository.objects.all()
    updated = 0

    for repo in repos:
        try:
            history: list = list(repo.star_history or [])

            # ── Append today's snapshot if not already present ─────────────
            if not any(h.get("date") == today_str for h in history):
                history.append({"date": today_str, "stars": repo.stars})
                # Keep only last 90 days
                cutoff_90d = (today - timedelta(days=90)).isoformat()
                history = [h for h in history if h.get("date", "") >= cutoff_90d]

            # ── Compute deltas ─────────────────────────────────────────────
            current_stars = repo.stars

            def stars_on_date(cutoff_date: "datetime.date") -> int:
                """Find closest snapshot on or before cutoff_date."""
                cutoff_str = cutoff_date.isoformat()
                candidates = [h for h in history if h.get("date", "") <= cutoff_str]
                if not candidates:
                    return current_stars  # no history → assume unchanged
                candidates.sort(key=lambda h: h["date"])
                return candidates[-1].get("stars", current_stars)

            stars_7d_ago = stars_on_date(cutoff_7d)
            stars_30d_ago = stars_on_date(cutoff_30d)

            delta_7d = current_stars - stars_7d_ago
            delta_30d = current_stars - stars_30d_ago

            velocity_7d = round(delta_7d / 7, 2)
            velocity_30d = round(delta_30d / 30, 2)

            # ── Classify ───────────────────────────────────────────────────
            stars_per_week = delta_7d
            if stars_per_week >= RISING_STAR_THRESHOLD:
                trend_class = Repository.TrendClass.RISING_STAR
            elif stars_per_week <= DECLINING_THRESHOLD:
                trend_class = Repository.TrendClass.DECLINING
            else:
                trend_class = Repository.TrendClass.STABLE

            # is_rising_star: young repo with explosive growth
            is_young = (
                repo.scraped_at is not None and repo.scraped_at.date() >= cutoff_new
            )
            is_rising_star = is_young and stars_per_week >= IS_RISING_THRESHOLD

            Repository.objects.filter(pk=repo.pk).update(
                star_history=history,
                stars_7d_delta=delta_7d,
                stars_30d_delta=delta_30d,
                velocity_7d=velocity_7d,
                velocity_30d=velocity_30d,
                trend_class=trend_class,
                is_rising_star=is_rising_star,
            )
            updated += 1

        except Exception as exc:
            logger.error("Velocity compute failed for repo %s: %s", repo.pk, exc)

    logger.info("TASK-602-B2: computed velocity for %d repos", updated)
    return {"updated": updated}
