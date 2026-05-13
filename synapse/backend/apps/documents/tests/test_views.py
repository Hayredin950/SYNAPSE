"""
Tests for the Documents app REST API views.

Covers:
  - DocumentGenerateView  (POST /api/v1/documents/generate/)
  - ProjectGenerateView   (POST /api/v1/documents/generate-project/)
  - DocumentListView      (GET  /api/v1/documents/)
  - DocumentDetailView    (GET/DELETE /api/v1/documents/<id>/)
  - DocumentDownloadView  (GET /api/v1/documents/<id>/download/)
"""

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from apps.documents.models import GeneratedDocument
from apps.users.models import User

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


def _make_user(email="doc_test@example.com", password="pass12345"):
    import uuid as _uuid

    username = email.split("@")[0] + "_" + _uuid.uuid4().hex[:4]
    return User.objects.create_user(username=username, email=email, password=password)


class DocumentGenerateViewTests(TestCase):
    """POST /api/v1/documents/generate/"""

    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/documents/generate/"

    def test_unauthenticated_returns_401(self):
        c = APIClient()
        resp = c.post(
            self.url, {"doc_type": "markdown", "title": "T", "prompt": "Write about AI"}
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_doc_type_returns_400(self):
        resp = self.client.post(
            self.url, {"title": "T", "prompt": "Write about AI today"}
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_doc_type_returns_400(self):
        resp = self.client.post(
            self.url,
            {"doc_type": "spreadsheet", "title": "T", "prompt": "Write about AI"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_prompt_too_short_returns_400(self):
        resp = self.client.post(
            self.url,
            {"doc_type": "markdown", "title": "T", "prompt": "Hi"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_title_returns_400(self):
        resp = self.client.post(
            self.url,
            {"doc_type": "markdown", "prompt": "Write about AI today"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_markdown_generation_returns_201(self):
        fake_result = ("Path: /tmp/test.md\nSome content", "/tmp/test.md")
        with patch(
            "apps.documents.views.DocumentGenerateView._call_tool",
            return_value=fake_result,
        ):
            resp = self.client.post(
                self.url,
                {
                    "doc_type": "markdown",
                    "title": "AI Report",
                    "prompt": "Write a comprehensive report on AI trends in 2025",
                    "author": "SYNAPSE",
                },
                format="json",
            )
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    def test_generated_doc_is_persisted_for_user(self):
        fake_result = ("Path: /tmp/test.md\nContent", "/tmp/test.md")
        with patch(
            "apps.documents.views.DocumentGenerateView._call_tool",
            return_value=fake_result,
        ):
            self.client.post(
                self.url,
                {
                    "doc_type": "markdown",
                    "title": "Persisted Doc",
                    "prompt": "Write about machine learning fundamentals clearly",
                },
                format="json",
            )
        self.assertTrue(
            GeneratedDocument.objects.filter(
                user=self.user, title="Persisted Doc"
            ).exists()
        )

    def test_tool_failure_returns_error(self):
        with patch(
            "apps.documents.views.DocumentGenerateView._call_tool",
            side_effect=Exception("generation failed"),
        ):
            resp = self.client.post(
                self.url,
                {
                    "doc_type": "pdf",
                    "title": "Fail Doc",
                    "prompt": "Write about neural networks in detail",
                },
                format="json",
            )
        self.assertIn(
            resp.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR],
        )

    def test_all_valid_doc_types_accepted_by_serializer(self):
        from apps.documents.serializers import DocumentGenerateSerializer

        for dt in ["pdf", "ppt", "word", "markdown"]:
            s = DocumentGenerateSerializer(
                data={
                    "doc_type": dt,
                    "title": "Test",
                    "prompt": "Write a detailed report on this topic",
                }
            )
            self.assertTrue(s.is_valid(), f"doc_type={dt} failed: {s.errors}")


class ProjectGenerateViewTests(TestCase):
    """POST /api/v1/documents/generate-project/"""

    def setUp(self):
        self.user = _make_user("proj_test@example.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/documents/generate-project/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().post(
            self.url, {"project_type": "django", "name": "myproject"}
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_project_type_returns_400(self):
        resp = self.client.post(
            self.url,
            {"project_type": "ruby_on_rails", "name": "bad"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_name_returns_400(self):
        resp = self.client.post(self.url, {"project_type": "django"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_name_chars_returns_400(self):
        resp = self.client.post(
            self.url,
            {"project_type": "django", "name": "my project!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_django_project_returns_success(self):
        fake_result = "Path: /tmp/myproject.zip\nProject created"
        with patch(
            "ai_engine.agents.project_tools._create_project", return_value=fake_result
        ):
            resp = self.client.post(
                self.url,
                {
                    "project_type": "django",
                    "name": "my_project",
                    "features": ["auth", "testing"],
                },
                format="json",
            )
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    def test_all_project_types_accepted_by_serializer(self):
        from apps.documents.serializers import ProjectGenerateSerializer

        for pt in ["django", "fastapi", "nextjs", "datascience", "react_lib"]:
            s = ProjectGenerateSerializer(data={"project_type": pt, "name": "testproj"})
            self.assertTrue(s.is_valid(), f"project_type={pt} failed: {s.errors}")


class DocumentListViewTests(TestCase):
    """GET /api/v1/documents/"""

    def setUp(self):
        self.user = _make_user("list_test@example.com")
        self.other_user = _make_user("other_list@example.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/documents/"

        for i, dt in enumerate(["markdown", "pdf", "markdown"]):
            GeneratedDocument.objects.create(
                user=self.user,
                doc_type=dt,
                title=f"Doc {i}",
                file_path=f"documents/doc_{i}.md",
                agent_prompt="prompt",
            )
        GeneratedDocument.objects.create(
            user=self.other_user,
            doc_type="pdf",
            title="Other Doc",
            file_path="documents/other.pdf",
            agent_prompt="prompt",
        )

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_only_own_documents(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        # Support both StandardPagination {success,data,meta} and DRF {results,[]}
        results = body.get("data") or body.get("results") or []
        if isinstance(results, dict):
            results = list(results.values())
        titles = [d["title"] for d in results]
        self.assertNotIn("Other Doc", titles)
        self.assertEqual(len(titles), 3)

    def test_filter_by_doc_type(self):
        resp = self.client.get(self.url + "?doc_type=markdown")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        results = body.get("data") or body.get("results") or []
        if isinstance(results, dict):
            results = list(results.values())
        for d in results:
            self.assertEqual(d["doc_type"], "markdown")

    def test_empty_list_returns_200(self):
        GeneratedDocument.objects.filter(user=self.user).delete()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class DocumentDetailViewTests(TestCase):
    """GET/DELETE /api/v1/documents/<id>/"""

    def setUp(self):
        self.user = _make_user("detail_test@example.com")
        self.other_user = _make_user("detail_other@example.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.doc = GeneratedDocument.objects.create(
            user=self.user,
            doc_type="markdown",
            title="Detail Doc",
            file_path="documents/detail.md",
            agent_prompt="prompt",
        )
        self.other_doc = GeneratedDocument.objects.create(
            user=self.other_user,
            doc_type="pdf",
            title="Other Detail",
            file_path="documents/other_detail.pdf",
            agent_prompt="prompt",
        )

    def _url(self, doc_id):
        return f"/api/v1/documents/{doc_id}/"

    def test_get_own_document_returns_200(self):
        resp = self.client.get(self._url(self.doc.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["title"], "Detail Doc")

    def test_get_other_user_document_returns_404(self):
        resp = self.client.get(self._url(self.other_doc.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_nonexistent_document_returns_404(self):
        resp = self.client.get(self._url(uuid.uuid4()))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_own_document_returns_204(self):
        resp = self.client.delete(self._url(self.doc.id))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(GeneratedDocument.objects.filter(id=self.doc.id).exists())

    def test_delete_other_user_document_returns_404(self):
        resp = self.client.delete(self._url(self.other_doc.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(GeneratedDocument.objects.filter(id=self.other_doc.id).exists())

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self._url(self.doc.id))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class DocumentDownloadViewTests(TestCase):
    """GET /api/v1/documents/<id>/download/"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.user = _make_user("download_test@example.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_doc(self, doc_type="markdown", with_file=True):
        rel_path = f"documents/test_{uuid.uuid4().hex}.md"
        if with_file:
            abs_path = Path(self.tmp_dir) / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text("# Test content")
        doc = GeneratedDocument.objects.create(
            user=self.user,
            doc_type=doc_type,
            title="Download Test",
            file_path=rel_path if with_file else "",
            agent_prompt="prompt",
        )
        return doc

    def test_download_existing_file_returns_200(self):
        doc = self._make_doc()
        with override_settings(MEDIA_ROOT=self.tmp_dir):
            resp = self.client.get(f"/api/v1/documents/{doc.id}/download/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("attachment", resp.get("Content-Disposition", ""))

    def test_download_no_file_path_returns_404(self):
        doc = self._make_doc(with_file=False)
        with override_settings(MEDIA_ROOT=self.tmp_dir):
            resp = self.client.get(f"/api/v1/documents/{doc.id}/download/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_missing_file_returns_404(self):
        """File path set but file deleted from disk."""
        doc = self._make_doc()
        (Path(self.tmp_dir) / doc.file_path).unlink(missing_ok=True)
        with override_settings(MEDIA_ROOT=self.tmp_dir):
            resp = self.client.get(f"/api/v1/documents/{doc.id}/download/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_other_user_document_returns_404(self):
        doc = self._make_doc()
        other_client = APIClient()
        other_client.force_authenticate(user=_make_user("dl_other@example.com"))
        with override_settings(MEDIA_ROOT=self.tmp_dir):
            resp = other_client.get(f"/api/v1/documents/{doc.id}/download/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_unauthenticated_returns_401(self):
        doc = self._make_doc()
        with override_settings(MEDIA_ROOT=self.tmp_dir):
            resp = APIClient().get(f"/api/v1/documents/{doc.id}/download/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
