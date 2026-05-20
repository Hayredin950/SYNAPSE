#!/usr/bin/env python3
"""
Direct content seeder — bypasses Celery task machinery entirely.
Fetches HackerNews articles and GitHub repos and saves them directly to the DB.
Run on startup when the DB has no articles/repos.
"""
import os
import sys
import logging

BACKEND_DIR = "/home/runner/workspace/synapse/backend"
SYNAPSE_DIR = "/home/runner/workspace/synapse"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, SYNAPSE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.replit")
os.environ.setdefault("DB_NAME", "heliumdb")
os.environ.setdefault("DB_USER", "postgres")
os.environ.setdefault("DB_PASSWORD", "password")
os.environ.setdefault("DB_HOST", "helium")
os.environ.setdefault("DB_PORT", "5432")

logging.basicConfig(level=logging.INFO, format="[seed] %(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def setup_django():
    import django
    django.setup()


def seed_hackernews(limit=80):
    import requests
    from django.utils import timezone
    from apps.articles.models import Article, Source

    log.info("Seeding HackerNews top stories (limit=%d)...", limit)
    hn_source, _ = Source.objects.get_or_create(
        url="https://news.ycombinator.com",
        defaults={"name": "Hacker News", "source_type": "news"},
    )

    try:
        resp = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15)
        resp.raise_for_status()
        story_ids = resp.json()[:limit]
    except Exception as exc:
        log.error("Failed to fetch HN story IDs: %s", exc)
        return 0

    import requests
    from datetime import datetime, timezone as dt_timezone

    saved = 0
    for sid in story_ids:
        try:
            item_resp = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=8
            )
            item_resp.raise_for_status()
            item = item_resp.json()

            if not item or item.get("type") != "story" or not item.get("url"):
                continue

            title = (item.get("title") or "").strip()
            url = item.get("url", "").strip()
            if not title or not url:
                continue

            published_at = None
            if item.get("time"):
                published_at = datetime.fromtimestamp(item["time"], tz=dt_timezone.utc)

            _, created = Article.objects.update_or_create(
                url=url,
                defaults={
                    "title": title[:1000],
                    "content": (item.get("text") or "")[:5000],
                    "author": (item.get("by") or "")[:300],
                    "source": hn_source,
                    "published_at": published_at,
                    "topic": "tech",
                    "tags": ["hackernews", "top"],
                    "trending_score": item.get("score", 0),
                    "metadata": {
                        "hn_id": sid,
                        "score": item.get("score", 0),
                        "descendants": item.get("descendants", 0),
                    },
                },
            )
            if created:
                saved += 1
        except Exception as exc:
            log.warning("Failed to save HN item %s: %s", sid, exc)
            continue

    log.info("HackerNews: %d new articles saved.", saved)
    return saved


def seed_github(days_back=7, limit=100):
    import requests
    from datetime import timedelta
    from django.utils import timezone
    from apps.repositories.models import Repository

    log.info("Seeding GitHub trending repos (days_back=%d, limit=%d)...", days_back, limit)
    since_date = (timezone.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    queries = [
        f"stars:>50 pushed:>{since_date}",
        f"created:>{since_date} stars:>10",
    ]

    saved = 0
    seen_ids = set()

    for query in queries:
        if saved >= limit:
            break
        try:
            resp = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "stars", "order": "desc", "per_page": min(50, limit)},
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 403:
                log.warning("GitHub API rate limited")
                break
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception as exc:
            log.warning("GitHub API request failed: %s", exc)
            continue

        for repo_data in items:
            if saved >= limit:
                break
            gh_id = repo_data.get("id")
            if not gh_id or gh_id in seen_ids:
                continue
            seen_ids.add(gh_id)
            try:
                from datetime import datetime, timezone as dt_timezone
                created_at_str = repo_data.get("created_at", "")[:10]
                repo_created = None
                if created_at_str:
                    repo_created = datetime.strptime(created_at_str, "%Y-%m-%d").replace(
                        tzinfo=dt_timezone.utc
                    )

                _, created = Repository.objects.update_or_create(
                    github_id=gh_id,
                    defaults={
                        "name": repo_data.get("name", "")[:200],
                        "full_name": repo_data.get("full_name", "")[:200],
                        "description": (repo_data.get("description") or "")[:2000],
                        "url": repo_data.get("html_url", ""),
                        "clone_url": repo_data.get("clone_url", ""),
                        "stars": repo_data.get("stargazers_count", 0),
                        "forks": repo_data.get("forks_count", 0),
                        "watchers": repo_data.get("watchers_count", 0),
                        "open_issues": repo_data.get("open_issues_count", 0),
                        "language": (repo_data.get("language") or "")[:100],
                        "topics": repo_data.get("topics", []),
                        "owner": (repo_data.get("owner") or {}).get("login", "")[:100],
                        "is_trending": repo_data.get("stargazers_count", 0) > 100,
                        "repo_created_at": repo_created,
                        "metadata": {"scraped_via": "seed_direct", "query": query},
                    },
                )
                if created:
                    saved += 1
            except Exception as exc:
                log.warning("Failed to save repo %s: %s", gh_id, exc)

    log.info("GitHub: %d new repos saved.", saved)
    return saved


ARTICLE_THRESHOLD = 20
REPO_THRESHOLD = 20


def needs_seeding():
    """Return (needs_articles, needs_repos) based on count thresholds."""
    from apps.articles.models import Article
    from apps.repositories.models import Repository
    needs_articles = Article.objects.count() < ARTICLE_THRESHOLD
    needs_repos = Repository.objects.count() < REPO_THRESHOLD
    return needs_articles, needs_repos


if __name__ == "__main__":
    setup_django()

    needs_articles, needs_repos = needs_seeding()

    if not needs_articles and not needs_repos:
        log.info("DB already has enough articles and repos — skipping seed.")
        sys.exit(0)

    if needs_articles:
        seed_hackernews(limit=80)
    else:
        log.info("Articles threshold met — skipping HN.")

    if needs_repos:
        seed_github(days_back=7, limit=80)
    else:
        log.info("Repos threshold met — skipping GitHub.")

    log.info("Seeding complete.")
