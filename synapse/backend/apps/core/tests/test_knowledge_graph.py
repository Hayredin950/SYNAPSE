"""
TASK-603 — AI Knowledge Graph tests.

Covers:
  B1 — KnowledgeNode + KnowledgeEdge models
  B2 — build_knowledge_graph Celery task
  B3 — API endpoints (graph, search, node detail)
"""

import pytest
from apps.core.models import KnowledgeEdge, KnowledgeNode
from apps.users.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework import status
from rest_framework.test import APIClient

# ── helpers ───────────────────────────────────────────────────────────────────


def make_user():
    import uuid

    u = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        username=f"kg_{u}", email=f"{u}@test.com", password="pass"
    )


def auth_client(user):
    c = APIClient()
    t = RefreshToken.for_user(user)
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {t.access_token}")
    return c


def make_node(name="Test", entity_type="concept", mention_count=1):
    return KnowledgeNode.objects.get_or_create(
        name=name, entity_type=entity_type, defaults={"mention_count": mention_count}
    )[0]


def make_edge(src, tgt, rel="related_to", weight=1.0):
    return KnowledgeEdge.objects.get_or_create(
        source=src, target=tgt, relation_type=rel, defaults={"weight": weight}
    )[0]


# ── B1: Model tests ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestKnowledgeNodeModel:
    def test_str(self):
        n = KnowledgeNode(name="Attention", entity_type="concept")
        assert "Attention" in str(n)
        assert "concept" in str(n)

    def test_unique_together(self):
        make_node("PyTorch", "tool")
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            KnowledgeNode.objects.create(name="PyTorch", entity_type="tool")

    def test_entity_type_choices(self):
        choices = [c[0] for c in KnowledgeNode.EntityType.choices]
        for t in ("concept", "paper", "repository", "author", "tool", "organization"):
            assert t in choices

    def test_defaults(self):
        n = make_node("GPT", "tool")
        assert n.source_ids == []
        assert n.metadata == {}
        assert n.mention_count == 1


@pytest.mark.django_db
class TestKnowledgeEdgeModel:
    def test_str(self):
        src = make_node("TransformerA", "paper")
        tgt = make_node("AttentionA", "concept")
        edge = make_edge(src, tgt, "cites")
        assert "cites" in str(edge)

    def test_unique_source_target_relation(self):
        from django.db import IntegrityError

        s = make_node("S", "concept")
        t = make_node("T", "tool")
        make_edge(s, t, "uses")
        with pytest.raises(IntegrityError):
            KnowledgeEdge.objects.create(source=s, target=t, relation_type="uses")

    def test_relation_choices(self):
        choices = [c[0] for c in KnowledgeEdge.RelationType.choices]
        for r in ("cites", "uses", "authored_by", "related_to", "built_with"):
            assert r in choices


# ── B2: Celery task tests ─────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuildKnowledgeGraphTask:
    def _run(self):
        from apps.core.tasks import build_knowledge_graph

        return build_knowledge_graph.apply().get()

    def test_returns_dict(self):
        result = self._run()
        assert "nodes_touched" in result
        assert "edges_created" in result

    def test_runs_on_empty_db(self):
        result = self._run()
        assert result["nodes_touched"] >= 0

    def test_idempotent(self):
        self._run()
        self._run()
        # Should not raise errors on second run


# ── B3: API endpoint tests ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestKnowledgeGraphView:
    URL = "/api/v1/knowledge-graph/"

    def test_requires_auth(self):
        resp = APIClient().get(self.URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_empty_graph(self):
        user = make_user()
        resp = auth_client(user).get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["nodes"] == []
        assert resp.data["data"]["edges"] == []

    def test_returns_nodes_and_edges(self):
        user = make_user()
        n1 = make_node("LLM", "concept", mention_count=10)
        n2 = make_node("GPT-4", "tool", mention_count=5)
        make_edge(n1, n2, "related_to")
        resp = auth_client(user).get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        node_ids = [n["id"] for n in resp.data["data"]["nodes"]]
        assert str(n1.id) in node_ids

    def test_filter_by_entity_type(self):
        user = make_user()
        make_node("Python", "tool")
        make_node("Attention", "concept")
        resp = auth_client(user).get(self.URL, {"type": "tool"})
        assert resp.status_code == status.HTTP_200_OK
        types = [n["entity_type"] for n in resp.data["data"]["nodes"]]
        assert all(t == "tool" for t in types)

    def test_center_node_bfs(self):
        user = make_user()
        center = make_node("BFS Center", "concept")
        neighbor = make_node("BFS Neighbor", "tool")
        make_edge(center, neighbor, "uses")
        resp = auth_client(user).get(self.URL, {"center": str(center.id), "depth": 1})
        assert resp.status_code == status.HTTP_200_OK
        node_ids = [n["id"] for n in resp.data["data"]["nodes"]]
        assert str(center.id) in node_ids

    def test_center_nonexistent_404(self):
        import uuid

        user = make_user()
        resp = auth_client(user).get(self.URL, {"center": str(uuid.uuid4())})
        assert resp.status_code == 404


@pytest.mark.django_db
class TestKnowledgeGraphSearch:
    URL = "/api/v1/knowledge-graph/search/"

    def test_requires_auth(self):
        resp = APIClient().get(self.URL, {"q": "test"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_q_400(self):
        user = make_user()
        resp = auth_client(user).get(self.URL)
        assert resp.status_code == 400

    def test_finds_node_by_name(self):
        user = make_user()
        make_node("Transformer Architecture", "concept")
        resp = auth_client(user).get(self.URL, {"q": "Transformer"})
        assert resp.status_code == status.HTTP_200_OK
        names = [n["name"] for n in resp.data["data"]]
        assert "Transformer Architecture" in names

    def test_filter_by_type(self):
        user = make_user()
        make_node("BERT", "tool")
        make_node("BERT Paper", "paper")
        resp = auth_client(user).get(self.URL, {"q": "BERT", "type": "paper"})
        data = resp.data["data"]
        assert all(n["entity_type"] == "paper" for n in data)


@pytest.mark.django_db
class TestKnowledgeNodeDetail:
    def test_requires_auth(self):
        import uuid

        resp = APIClient().get(f"/api/v1/knowledge-graph/nodes/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_node_with_edges(self):
        user = make_user()
        n1 = make_node("RLHF", "concept")
        n2 = make_node("ChatGPT", "tool")
        make_edge(n1, n2, "built_with")
        resp = auth_client(user).get(f"/api/v1/knowledge-graph/nodes/{n1.id}/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data["data"]
        assert data["name"] == "RLHF"
        assert "outgoing_edges" in data
        assert "incoming_edges" in data

    def test_nonexistent_404(self):
        import uuid

        user = make_user()
        resp = auth_client(user).get(f"/api/v1/knowledge-graph/nodes/{uuid.uuid4()}/")
        assert resp.status_code == 404

    def test_response_fields(self):
        user = make_user()
        n = make_node("Diffusion Models", "concept")
        resp = auth_client(user).get(f"/api/v1/knowledge-graph/nodes/{n.id}/")
        data = resp.data["data"]
        for field in (
            "id",
            "name",
            "entity_type",
            "mention_count",
            "outgoing_edges",
            "incoming_edges",
        ):
            assert field in data
