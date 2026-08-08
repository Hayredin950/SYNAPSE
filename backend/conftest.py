import os
import sys

# Ensure both backend/ and the repo root (for ai_engine) are on the path
_backend_dir = os.path.dirname(__file__)
_repo_root = os.path.dirname(_backend_dir)
sys.path.insert(0, _backend_dir)
sys.path.insert(0, _repo_root)

# Must be set BEFORE Django imports anything
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"

# Docker maps synapse_postgres:5432 -> host:5433
# Only override DB connection vars when not running in CI.
# CI environments (GitHub Actions, GitLab CI, CircleCI, etc.) set their own
# DB_HOST/DB_PORT via secrets or service containers — don't override them.
_IN_CI = any(
    os.environ.get(v)
    for v in [
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "CIRCLECI",
        "TRAVIS",
        "JENKINS_URL",
    ]
)
if not _IN_CI:
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "5433")
