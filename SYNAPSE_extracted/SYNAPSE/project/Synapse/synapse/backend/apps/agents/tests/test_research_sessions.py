"""
TASK-601 — Research Session API tests.
"""

import pytest
from apps.agents.models import ResearchSession
from apps.users.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework import status
from rest_framework.test import APIClient


def make_user(username, email):
    return User.objects.create_user(
        username=username, email=email, password="testpass123"
    )


def auth_client(user):
    c = APIClient()
    token = RefreshToken.for_user(user)
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return c


@pytest.fixture
def user(db):
    return make_user("researcher", "researcher@example.com")


@pytest.fixture
def client_auth(user):
    return auth_client(user)


@pytest.mark.django_db
class TestResearchSessionModel:
    def test_str(self, user):
        s = ResearchSession(user=user, query="How does attention work in transformers?")
        assert "attention" in str(s)
        assert s.status == ResearchSession.Status.QUEUED

    def test_defaults(self, db, user):
        s = ResearchSession.objects.create(user=user, query="Test query")
        assert s.report == ""
        assert s.sources == []
        assert s.sub_questions == []
        assert s.completed_at is None


@pytest.mark.django_db
class TestResearchSessionListCreate:
    URL = "/api/v1/agents/research/"

    def test_unauthenticated_401(self):
        resp = APIClient().post(self.URL, {"query": "test"}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_session(self, client_auth):
        resp = client_auth.post(
            self.URL, {"query": "Explain LLM attention mechanisms"}, format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["data"]["status"] == "queued"
        assert resp.data["data"]["query"] == "Explain LLM attention mechanisms"

    def test_empty_query_400(self, client_auth):
        resp = client_auth.post(self.URL, {"query": ""}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_query_400(self, client_auth):
        resp = client_auth.post(self.URL, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_query_too_long_400(self, client_auth):
        resp = client_auth.post(self.URL, {"query": "x" * 2001}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_sessions(self, client_auth, user):
        ResearchSession.objects.create(user=user, query="Q1")
        ResearchSession.objects.create(user=user, query="Q2")
        resp = client_auth.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["data"]) == 2

    def test_list_only_own_sessions(self, db, user):
        other = make_user("other", "other@example.com")
        ResearchSession.objects.create(user=other, query="Other query")
        c = auth_client(user)
        resp = c.get(self.URL)
        assert resp.data["data"] == []


@pytest.mark.django_db
class TestResearchSessionDetail:
    def test_get_own_session(self, client_auth, user):
        s = ResearchSession.objects.create(
            user=user, query="My question", report="My report"
        )
        resp = client_auth.get(f"/api/v1/agents/research/{s.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["report"] == "My report"

    def test_cannot_access_others_session(self, db, user):
        other = make_user("spy2", "spy2@example.com")
        s = ResearchSession.objects.create(user=other, query="Secret")
        c = auth_client(user)
        resp = c.get(f"/api/v1/agents/research/{s.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_response_fields(self, client_auth, user):
        s = ResearchSession.objects.create(user=user, query="Fields test")
        resp = client_auth.get(f"/api/v1/agents/research/{s.id}/")
        data = resp.data["data"]
        for field in (
            "id",
            "query",
            "status",
            "report",
            "sources",
            "sub_questions",
            "created_at",
        ):
            assert field in data
