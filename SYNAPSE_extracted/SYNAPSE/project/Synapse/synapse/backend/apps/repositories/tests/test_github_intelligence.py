"""
TASK-602 — GitHub Intelligence Dashboard tests.

Covers:
  B1 — Repository velocity fields (model defaults, TrendClass choices)
  B2 — compute_star_velocity Celery task (delta, velocity, classification)
  B3 — API endpoints (trending-velocity, ecosystem, repo-analysis)
"""

import uuid as _uuid
from datetime import date, timedelta

import pytest
from apps.repositories.models import Repository

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

# ── helpers ───────────────────────────────────────────────────────────────────



def make_repo(**kwargs):
    defaults = dict(
        github_id=str(_uuid.uuid4().int)[:10],  # unique numeric-style github_id
        full_name="owner/testrepo",
        url="https://github.com/owner/testrepo",
        description="A test repo",
        language="Python",
        stars=1000,
        forks=100,
        topics=["ml", "llm"],
        is_trending=True,
    )
    defaults.update(kwargs)
    # ensure full_name and url are unique per call if not overridden
    if "full_name" not in kwargs:
        defaults["full_name"] = f"owner/repo-{defaults['github_id']}"
    if "url" not in kwargs:
        defaults["url"] = f"https://github.com/{defaults['full_name']}"
    return Repository.objects.create(**defaults)


# ── B1: Model velocity fields ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestRepositoryVelocityFields:
    def test_velocity_defaults(self):
        repo = make_repo()
        assert repo.stars_7d_delta == 0
        assert repo.stars_30d_delta == 0
        assert repo.velocity_7d == 0.0
        assert repo.velocity_30d == 0.0
        assert repo.trend_class == Repository.TrendClass.STABLE
        assert repo.is_rising_star is False
        assert repo.star_history == []

    def test_trend_class_choices(self):
        choices = [c[0] for c in Repository.TrendClass.choices]
        assert "rising_star" in choices
        assert "stable" in choices
        assert "declining" in choices

    def test_velocity_fields_persisted(self):
        repo = make_repo()
        repo.stars_7d_delta = 500
        repo.velocity_7d = 71.4
        repo.trend_class = Repository.TrendClass.RISING_STAR
        repo.is_rising_star = True
        repo.save()
        repo.refresh_from_db()
        assert repo.stars_7d_delta == 500
        assert repo.velocity_7d == 71.4
        assert repo.trend_class == "rising_star"
        assert repo.is_rising_star is True

    def test_star_history_json(self):
        history = [
            {"date": "2026-04-01", "stars": 900},
            {"date": "2026-04-04", "stars": 1000},
        ]
        repo = make_repo(star_history=history)
        repo.refresh_from_db()
        assert len(repo.star_history) == 2
        assert repo.star_history[0]["date"] == "2026-04-01"


# ── B2: compute_star_velocity task ───────────────────────────────────────────


@pytest.mark.django_db
class TestComputeStarVelocity:

    def _run_task(self):
        from apps.repositories.analytics import compute_star_velocity

        result = compute_star_velocity.apply()
        return result.get()

    def test_returns_updated_count(self):
        make_repo(full_name="owner/r1", url="https://g.com/r1")
        make_repo(full_name="owner/r2", url="https://g.com/r2")
        result = self._run_task()
        assert result["updated"] == 2

    def test_appends_star_snapshot(self):
        repo = make_repo(full_name="owner/snap", url="https://g.com/snap")
        self._run_task()
        repo.refresh_from_db()
        today_str = timezone.now().date().isoformat()
        assert any(h.get("date") == today_str for h in repo.star_history)

    def test_rising_star_classification(self):
        """Repo with large delta in history gets rising_star trend class."""
        today = timezone.now().date()
        old_str = (today - timedelta(days=7)).isoformat()
        # Simulate 500 stars gained in 7 days
        history = [{"date": old_str, "stars": 500}]
        repo = make_repo(
            full_name="owner/rising",
            url="https://g.com/rising",
            stars=600,
            star_history=history,
        )
        self._run_task()
        repo.refresh_from_db()
        assert repo.trend_class == Repository.TrendClass.RISING_STAR
        assert repo.stars_7d_delta == 100  # 600 - 500

    def test_stable_classification(self):
        today = timezone.now().date()
        old_str = (today - timedelta(days=7)).isoformat()
        history = [{"date": old_str, "stars": 990}]
        repo = make_repo(
            full_name="owner/stable",
            url="https://g.com/stable",
            stars=1000,
            star_history=history,
        )
        self._run_task()
        repo.refresh_from_db()
        assert repo.trend_class == Repository.TrendClass.STABLE  # delta=10, below 50

    def test_declining_classification(self):
        today = timezone.now().date()
        old_str = (today - timedelta(days=7)).isoformat()
        history = [{"date": old_str, "stars": 1020}]
        repo = make_repo(
            full_name="owner/declining",
            url="https://g.com/declining",
            stars=1000,
            star_history=history,
        )
        self._run_task()
        repo.refresh_from_db()
        assert repo.trend_class == Repository.TrendClass.DECLINING  # delta = -20

    def test_velocity_7d_calculated_correctly(self):
        today = timezone.now().date()
        old_str = (today - timedelta(days=7)).isoformat()
        history = [{"date": old_str, "stars": 300}]
        repo = make_repo(
            full_name="owner/vel",
            url="https://g.com/vel",
            stars=1000,
            star_history=history,
        )
        self._run_task()
        repo.refresh_from_db()
        # delta_7d = 700, velocity = 700/7 = 100.0
        assert repo.velocity_7d == 100.0

    def test_idempotent_snapshot(self):
        """Running twice on same day should not duplicate snapshot."""
        repo = make_repo(full_name="owner/idem", url="https://g.com/idem")
        self._run_task()
        self._run_task()
        repo.refresh_from_db()
        today_str = timezone.now().date().isoformat()
        count = sum(1 for h in repo.star_history if h.get("date") == today_str)
        assert count == 1

    def test_old_history_pruned_to_90_days(self):
        today = timezone.now().date()
        old_date = (today - timedelta(days=100)).isoformat()  # >90 days ago
        history = [{"date": old_date, "stars": 100}]
        repo = make_repo(
            full_name="owner/prune",
            url="https://g.com/prune",
            star_history=history,
        )
        self._run_task()
        repo.refresh_from_db()
        # old snapshot should be pruned
        assert not any(h.get("date") == old_date for h in repo.star_history)


# ── B3: API endpoint tests ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGitHubTrendingView:
    URL = "/api/v1/repos/trending-velocity/"

    def test_returns_200(self):
        make_repo()
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_200_OK

    def test_result_fields(self):
        make_repo(velocity_7d=50.0, stars_7d_delta=350)
        resp = APIClient().get(self.URL)
        assert resp.data["success"] is True
        if resp.data["data"]:
            repo = resp.data["data"][0]
            for field in (
                "full_name",
                "url",
                "stars",
                "velocity_7d",
                "trend_class",
                "stars_7d_delta",
            ):
                assert field in repo

    def test_filter_by_language(self):
        make_repo(
            full_name="o/py", url="https://g.com/py", language="Python", stars=500
        )
        make_repo(
            full_name="o/ts", url="https://g.com/ts", language="TypeScript", stars=400
        )
        resp = APIClient().get(self.URL, {"language": "Python"})
        data = resp.data["data"]
        assert all(r["language"] == "Python" for r in data)

    def test_sorted_by_velocity(self):
        make_repo(full_name="o/slow", url="https://g.com/slow", velocity_7d=5.0)
        make_repo(full_name="o/fast", url="https://g.com/fast", velocity_7d=100.0)
        resp = APIClient().get(self.URL)
        data = resp.data["data"]
        if len(data) >= 2:
            velocities = [r["velocity_7d"] for r in data]
            assert velocities == sorted(velocities, reverse=True)


@pytest.mark.django_db
class TestGitHubEcosystemView:

    def test_returns_ecosystem_stats(self):
        make_repo(language="Rust", velocity_7d=20.0)
        make_repo(
            full_name="o/r2", url="https://g.com/r2", language="Rust", velocity_7d=30.0
        )
        resp = APIClient().get("/api/v1/repos/ecosystem/Rust/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data["data"]
        assert data["language"] == "Rust"
        assert data["total_repos"] == 2
        assert "avg_velocity_7d" in data
        assert "top_repos" in data

    def test_unknown_language_404(self):
        resp = APIClient().get("/api/v1/repos/ecosystem/CobolXYZ/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestGitHubRepoAnalysisView:

    def test_returns_full_analysis(self):
        repo = make_repo(star_history=[{"date": "2026-04-01", "stars": 900}])
        resp = APIClient().get(f"/api/v1/repos/{repo.id}/analysis/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data["data"]
        for field in (
            "id",
            "full_name",
            "velocity_7d",
            "star_history",
            "similar_repos",
        ):
            assert field in data

    def test_nonexistent_returns_404(self):
        import uuid

        resp = APIClient().get(f"/api/v1/repos/{uuid.uuid4()}/analysis/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
