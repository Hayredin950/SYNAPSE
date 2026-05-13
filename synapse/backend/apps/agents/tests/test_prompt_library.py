"""
TASK-306 — Prompt Library tests.

Covers:
  B1 — PromptTemplate + PromptUpvote models (unique constraint, str repr, ordering)
  B2 — All 6 API endpoints:
        GET  /api/v1/agents/prompts/          list + filter
        POST /api/v1/agents/prompts/          create
        GET  /api/v1/agents/prompts/{id}/     detail
        POST /api/v1/agents/prompts/{id}/use/    increment use_count
        POST /api/v1/agents/prompts/{id}/upvote/ toggle upvote
        GET  /api/v1/agents/prompts/my/       own prompts
"""

import uuid

import pytest
from apps.agents.models import PromptTemplate, PromptUpvote
from apps.users.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework import status
from rest_framework.test import APIClient

# ─────────────────────────── helpers ─────────────────────────────────────────


def make_user(username, email):
    return User.objects.create_user(
        username=username, email=email, password="testpass123"
    )


def auth_client(user):
    c = APIClient()
    token = RefreshToken.for_user(user)
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return c


def make_prompt(author, **kwargs):
    defaults = dict(
        title="Test Prompt",
        description="A test prompt",
        content="Summarise the following text in 3 bullet points: {text}",
        category="research",
        is_public=True,
    )
    defaults.update(kwargs)
    return PromptTemplate.objects.create(author=author, **defaults)


# ─────────────────────────── fixtures ────────────────────────────────────────


@pytest.fixture
def user(db):
    return make_user("alice", "alice@example.com")


@pytest.fixture
def other_user(db):
    return make_user("bob", "bob@example.com")


@pytest.fixture
def client_auth(user):
    return auth_client(user)


@pytest.fixture
def other_client(other_user):
    return auth_client(other_user)


@pytest.fixture
def prompt(db, user):
    return make_prompt(user)


# ─────────────────────── B1: Model tests ─────────────────────────────────────


@pytest.mark.django_db
class TestPromptTemplateModel:
    def test_str(self, prompt):
        assert "Test Prompt" in str(prompt)
        assert "research" in str(prompt)

    def test_defaults(self, prompt):
        assert prompt.use_count == 0
        assert prompt.upvotes == 0
        assert prompt.is_public is True

    def test_ordering_by_upvotes(self, db, user):
        p1 = make_prompt(user, title="Low", upvotes=1)
        p2 = make_prompt(user, title="High", upvotes=10)
        qs = list(PromptTemplate.objects.all())
        assert qs[0].title == "High"

    def test_categories(self, db, user):
        for cat in [
            "research",
            "coding",
            "writing",
            "analysis",
            "business",
            "creative",
        ]:
            make_prompt(user, title=f"p-{cat}", category=cat)
        assert PromptTemplate.objects.filter(category="coding").exists()


@pytest.mark.django_db
class TestPromptUpvoteModel:
    def test_unique_per_user_prompt(self, db, user, prompt):
        from django.db import IntegrityError

        PromptUpvote.objects.create(user=user, prompt=prompt)
        with pytest.raises(IntegrityError):
            PromptUpvote.objects.create(user=user, prompt=prompt)


# ─────────────────────── B2: API tests ───────────────────────────────────────


@pytest.mark.django_db
class TestPromptListCreate:
    URL = "/api/v1/agents/prompts/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_public_prompts(self, client_auth, prompt):
        resp = client_auth.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        # handles paginated or direct response
        results = resp.data.get("results") or resp.data.get("data", [])
        ids = [p["id"] for p in results]
        assert str(prompt.id) in ids

    def test_private_prompt_not_listed(self, client_auth, user):
        priv = make_prompt(user, is_public=False)
        resp = client_auth.get(self.URL)
        results = resp.data.get("results") or resp.data.get("data", [])
        ids = [p["id"] for p in results]
        assert str(priv.id) not in ids

    def test_filter_by_category(self, client_auth, user):
        make_prompt(user, title="Code one", category="coding")
        make_prompt(user, title="Research one", category="research")
        resp = client_auth.get(self.URL, {"category": "coding"})
        results = resp.data.get("results") or resp.data.get("data", [])
        assert all(p["category"] == "coding" for p in results)

    def test_sort_newest(self, client_auth, prompt):
        resp = client_auth.get(self.URL, {"sort": "newest"})
        assert resp.status_code == status.HTTP_200_OK

    def test_create_prompt(self, client_auth):
        payload = {
            "title": "My New Prompt",
            "description": "Does something cool",
            "content": "Write a detailed analysis of {topic} in 5 paragraphs.",
            "category": "writing",
            "is_public": True,
        }
        resp = client_auth.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["data"]["title"] == "My New Prompt"

    def test_create_requires_title_min_length(self, client_auth):
        resp = client_auth.post(
            self.URL,
            {
                "title": "AB",
                "content": "Long enough content here",
                "category": "coding",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_requires_content_min_length(self, client_auth):
        resp = client_auth.post(
            self.URL,
            {"title": "Valid Title", "content": "Short", "category": "coding"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPromptDetail:
    def test_get_public_prompt(self, client_auth, prompt):
        resp = client_auth.get(f"/api/v1/agents/prompts/{prompt.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["id"] == str(prompt.id)
        assert "content" in resp.data["data"]

    def test_get_own_private_prompt(self, client_auth, user):
        priv = make_prompt(user, is_public=False)
        resp = client_auth.get(f"/api/v1/agents/prompts/{priv.id}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_other_user_cannot_see_private(self, other_client, user):
        priv = make_prompt(user, is_public=False)
        resp = other_client.get(f"/api/v1/agents/prompts/{priv.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_nonexistent_returns_404(self, client_auth):
        resp = client_auth.get(f"/api/v1/agents/prompts/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPromptUse:
    def test_increments_use_count(self, client_auth, prompt):
        assert prompt.use_count == 0
        resp = client_auth.post(f"/api/v1/agents/prompts/{prompt.id}/use/")
        assert resp.status_code == status.HTTP_200_OK
        assert "content" in resp.data["data"]
        prompt.refresh_from_db()
        assert prompt.use_count == 1

    def test_returns_prompt_content(self, client_auth, prompt):
        resp = client_auth.post(f"/api/v1/agents/prompts/{prompt.id}/use/")
        assert resp.data["data"]["content"] == prompt.content

    def test_private_not_accessible_by_others(self, other_client, user):
        priv = make_prompt(user, is_public=False)
        resp = other_client.post(f"/api/v1/agents/prompts/{priv.id}/use/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPromptUpvote:
    def test_upvote_increments_count(self, client_auth, prompt):
        resp = client_auth.post(f"/api/v1/agents/prompts/{prompt.id}/upvote/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["upvoted"] is True
        prompt.refresh_from_db()
        assert prompt.upvotes == 1

    def test_upvote_toggle_removes(self, client_auth, prompt):
        client_auth.post(f"/api/v1/agents/prompts/{prompt.id}/upvote/")
        resp = client_auth.post(f"/api/v1/agents/prompts/{prompt.id}/upvote/")
        assert resp.data["data"]["upvoted"] is False
        prompt.refresh_from_db()
        assert prompt.upvotes == 0

    def test_two_users_can_upvote(self, client_auth, other_client, prompt):
        client_auth.post(f"/api/v1/agents/prompts/{prompt.id}/upvote/")
        other_client.post(f"/api/v1/agents/prompts/{prompt.id}/upvote/")
        prompt.refresh_from_db()
        assert prompt.upvotes == 2


@pytest.mark.django_db
class TestMyPrompts:
    URL = "/api/v1/agents/prompts/my/"

    def test_returns_only_own_prompts(
        self, client_auth, other_client, user, other_user
    ):
        mine = make_prompt(user, title="Mine")
        theirs = make_prompt(other_user, title="Theirs")
        resp = client_auth.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        ids = [p["id"] for p in resp.data["data"]]
        assert str(mine.id) in ids
        assert str(theirs.id) not in ids

    def test_includes_private_prompts(self, client_auth, user):
        priv = make_prompt(user, is_public=False, title="Private")
        resp = client_auth.get(self.URL)
        ids = [p["id"] for p in resp.data["data"]]
        assert str(priv.id) in ids

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
