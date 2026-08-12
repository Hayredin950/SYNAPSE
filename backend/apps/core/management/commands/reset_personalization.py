"""
Management command: reset_personalization

Clears per-user personalization data so two accounts can be re-tested from a
clean slate. Deletes:

  * DailyBriefing rows (the "Today's Brief" cards)
  * user→content link junctions (user_articles, user_repositories,
    user_papers, user_videos, user_tweets) — these drive the "linked items"
    preference tier of the briefing generator
  * Growth NPS feedback submissions (growth_user_feedback)

Optional (--interests): also clears OnboardingPreferences.interests and the
InterestProfileBuilder profile so the user can redo the wizard.

The scraped content itself (articles, papers, repos, videos, tweets) is GLOBAL
and shared across users — it is intentionally NOT deleted.

Usage:
  python manage.py reset_personalization                       # all users
  python manage.py reset_personalization --email a@b.c         # one user
  python manage.py reset_personalization --interests          # also wizard data
  python manage.py reset_personalization --yes                # skip confirmation
"""

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

logger  # noqa: PLC0105  (keep logger import pattern consistent with repo)


class Command(BaseCommand):
    help = "Clear per-user personalization data (briefings, links, feedback) for a clean re-test"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default=None,
            help="Only reset data for this user email (default: all users)",
        )
        parser.add_argument(
            "--interests",
            action="store_true",
            help="Also clear onboarding interests / InterestProfileBuilder profile",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the confirmation prompt",
        )

    def handle(self, *args, **options):
        email = options["email"]
        include_interests = options["interests"]
        assume_yes = options["yes"]

        from apps.articles.models import UserArticle
        from apps.core.models import DailyBriefing
        from apps.papers.models import UserPaper
        from apps.repositories.models import UserRepository
        from apps.tweets.models import UserTweet
        from apps.users.models import User
        from apps.videos.models import UserVideo

        try:
            from apps.growth.models import UserFeedback
        except ImportError:  # growth app not installed in this environment
            UserFeedback = None

        def _filter(qs):
            return qs.filter(user__email=email) if email else qs

        # ── Build the deletion plan ─────────────────────────────────────────
        plan = [
            ("daily briefings", _filter(DailyBriefing.objects.all())),
            ("article links", _filter(UserArticle.objects.all())),
            ("repository links", _filter(UserRepository.objects.all())),
            ("paper links", _filter(UserPaper.objects.all())),
            ("video links", _filter(UserVideo.objects.all())),
            ("tweet links", _filter(UserTweet.objects.all())),
        ]
        if UserFeedback is not None:
            plan.append(("NPS feedback", _filter(UserFeedback.objects.all())))

        counts = {name: qs.count() for name, qs in plan}

        # ── Confirmation ────────────────────────────────────────────────────
        self.stdout.write("Plan — will delete:")
        for name, qs in plan:
            self.stdout.write(f"  · {counts[name]:>6}  {name}")
        if include_interests:
            # Just report; actual clearing happens below.
            self.stdout.write("  ·   ALL  onboarding interests + interest profiles")

        if not assume_yes:
            answer = input("\nType 'yes' to continue: ").strip().lower()
            if answer != "yes":
                self.stdout.write(self.style.WARNING("Aborted — nothing was deleted."))
                return

        # ── Execute ─────────────────────────────────────────────────────────
        deleted = {}
        for name, qs in plan:
            try:
                deleted[name] = qs.delete()[0]
            except Exception as exc:  # noqa: BLE001 — report and continue
                logger.warning("reset_personalization: %s delete failed: %s", name, exc)
                deleted[name] = 0

        if include_interests:
            if email:
                user = User.objects.filter(email=email).first()
                if user:
                    user_qs = [user]
                else:
                    user_qs = []
            else:
                user_qs = list(User.objects.all())
            removed_prefs = 0
            removed_profiles = 0
            for user in user_qs:
                try:
                    prefs = getattr(user, "onboarding_prefs", None)
                    if prefs and prefs.interests:
                        prefs.interests = []
                        prefs.completed = False
                        prefs.save(
                            update_fields=["interests", "completed", "updated_at"]
                        )
                        removed_prefs += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Could not clear onboarding prefs for %s: %s", user.email, exc
                    )
                try:
                    prefs_dict = dict(user.preferences or {})
                    if prefs_dict.pop("interest_profile", None):
                        user.preferences = prefs_dict
                        user.save(update_fields=["preferences"])
                        removed_profiles += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Could not clear interest profile for %s: %s", user.email, exc
                    )
            deleted["onboarding interests"] = removed_prefs + removed_profiles

        # ── Report ──────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS("\nDone — deleted:"))
        for name, qs in plan:
            self.stdout.write(f"  · {deleted.get(name, 0):>6}  {name}")
        if include_interests:
            self.stdout.write(
                f"  · {deleted.get('onboarding interests', 0):>6}  onboarding interests + profiles"
            )

        # ── Next steps ──────────────────────────────────────────────────────
        if email:
            self.stdout.write(
                self.style.WARNING(
                    "\nNext: ask the user to re-run their workflows (or redo onboarding), "
                    "then refresh /home — the briefing will regenerate from their interests."
                )
            )
