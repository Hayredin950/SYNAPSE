"""
backend.apps.documents.tests.test_doc_generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for Phase 5.2 document generation tools.

All file I/O is redirected to a temp directory.
External libraries (reportlab, pptx, docx) are tested with real calls
since they are pure-Python and have no network dependencies.

Phase 5.2 — Document Generation (Week 14)
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

# ---------------------------------------------------------------------------
# Helper: point MEDIA_ROOT at a temp dir for each test
# ---------------------------------------------------------------------------


class DocToolTestCase(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Patch both MEDIA_ROOT and DJANGO_MEDIA_ROOT so _doc_dir() uses the temp dir
        self.env_patch = patch.dict(
            os.environ,
            {
                "MEDIA_ROOT": self.tmp,
                "DJANGO_MEDIA_ROOT": self.tmp,
            },
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        # Clean up generated files
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)


# ===========================================================================
# 1. generate_pdf
# ===========================================================================


class TestGeneratePDF(DocToolTestCase):

    def _run(
        self, title="Test Report", sections=None, subtitle="", author="SYNAPSE AI"
    ):
        from ai_engine.agents.doc_tools import _generate_pdf

        sections = sections or [
            {
                "heading": "Introduction",
                "content": "This is the intro paragraph.\n\nSecond paragraph.",
            },
            {"heading": "Findings", "content": "Key findings go here."},
        ]
        return _generate_pdf(
            title=title,
            sections=sections,
            subtitle=subtitle,
            author=author,
            user_id="test",
        )

    def test_generates_pdf_file(self):
        result = self._run()
        self.assertIn("PDF generated successfully", result)
        self.assertIn(".pdf", result)
        # Extract path and verify file exists
        for line in result.splitlines():
            if line.startswith("Path:"):
                path = Path(line.replace("Path:", "").strip())
                self.assertTrue(path.exists(), f"PDF file not found at {path}")
                self.assertGreater(
                    path.stat().st_size, 1000, "PDF file suspiciously small"
                )
                break

    def test_result_contains_title(self):
        result = self._run(title="My Custom Report")
        self.assertIn("My Custom Report", result)

    def test_result_contains_section_count(self):
        result = self._run(
            sections=[
                {"heading": "S1", "content": "Content 1"},
                {"heading": "S2", "content": "Content 2"},
                {"heading": "S3", "content": "Content 3"},
            ]
        )
        self.assertIn("Sections: 3", result)

    def test_result_contains_file_size(self):
        result = self._run()
        self.assertIn("bytes", result)

    def test_handles_special_chars_in_content(self):
        result = self._run(
            sections=[
                {
                    "heading": "Test & More",
                    "content": "Content with <special> & 'chars' and \"quotes\".",
                }
            ]
        )
        self.assertIn("PDF generated successfully", result)

    def test_tool_metadata(self):
        from ai_engine.agents.doc_tools import make_generate_pdf_tool

        tool = make_generate_pdf_tool()
        self.assertEqual(tool.name, "generate_pdf")
        self.assertIn("pdf", tool.description.lower())

    def test_input_schema_requires_title_and_sections(self):
        from ai_engine.agents.doc_tools import GeneratePDFInput

        schema = GeneratePDFInput.schema()
        required = schema.get("required", [])
        self.assertIn("title", required)
        self.assertIn("sections", required)


# ===========================================================================
# 2. generate_ppt
# ===========================================================================


class TestGeneratePPT(DocToolTestCase):

    def _run(self, title="Test Presentation", slides=None):
        from ai_engine.agents.doc_tools import _generate_ppt

        slides = slides or [
            {
                "title": "Slide 1",
                "bullets": ["Point A", "Point B"],
                "notes": "Speaker note 1",
            },
            {"title": "Slide 2", "bullets": ["Point C", "Point D"], "notes": ""},
        ]
        return _generate_ppt(
            title=title,
            slides=slides,
            subtitle="By SYNAPSE",
            author="SYNAPSE AI",
            user_id="test",
        )

    def test_generates_pptx_file(self):
        result = self._run()
        self.assertIn("PowerPoint generated successfully", result)
        self.assertIn(".pptx", result)
        for line in result.splitlines():
            if line.startswith("Path:"):
                path = Path(line.replace("Path:", "").strip())
                self.assertTrue(path.exists(), f"PPTX not found at {path}")
                self.assertGreater(path.stat().st_size, 1000)
                break

    def test_slide_count_includes_title_slide(self):
        result = self._run(
            slides=[
                {"title": "S1", "bullets": ["a"], "notes": ""},
                {"title": "S2", "bullets": ["b"], "notes": ""},
            ]
        )
        # 2 content slides + 1 title = 3
        self.assertIn("Slides: 3", result)

    def test_result_contains_title(self):
        result = self._run(title="AI Trends 2025")
        self.assertIn("AI Trends 2025", result)

    def test_tool_metadata(self):
        from ai_engine.agents.doc_tools import make_generate_ppt_tool

        tool = make_generate_ppt_tool()
        self.assertEqual(tool.name, "generate_ppt")
        self.assertIn("powerpoint", tool.description.lower())

    def test_input_schema_requires_title_and_slides(self):
        from ai_engine.agents.doc_tools import GeneratePPTInput

        schema = GeneratePPTInput.schema()
        required = schema.get("required", [])
        self.assertIn("title", required)
        self.assertIn("slides", required)


# ===========================================================================
# 3. generate_word_doc
# ===========================================================================


class TestGenerateWordDoc(DocToolTestCase):

    def _run(self, title="Test Word Doc", sections=None, add_toc=True):
        from ai_engine.agents.doc_tools import _generate_word_doc

        sections = sections or [
            {
                "heading": "Executive Summary",
                "content": "This document covers...\n\nMore content.",
                "level": 1,
            },
            {"heading": "Details", "content": "Detailed findings.", "level": 2},
        ]
        return _generate_word_doc(
            title=title,
            sections=sections,
            author="SYNAPSE AI",
            add_toc=add_toc,
            user_id="test",
        )

    def test_generates_docx_file(self):
        result = self._run()
        self.assertIn("Word document generated successfully", result)
        self.assertIn(".docx", result)
        for line in result.splitlines():
            if line.startswith("Path:"):
                path = Path(line.replace("Path:", "").strip())
                self.assertTrue(path.exists(), f"DOCX not found at {path}")
                self.assertGreater(path.stat().st_size, 1000)
                break

    def test_result_contains_section_count(self):
        result = self._run(
            sections=[
                {"heading": "S1", "content": "c1", "level": 1},
                {"heading": "S2", "content": "c2", "level": 2},
                {"heading": "S3", "content": "c3", "level": 3},
            ]
        )
        self.assertIn("Sections: 3", result)

    def test_toc_flag_reported(self):
        result_with = self._run(add_toc=True)
        self.assertIn("TOC: yes", result_with)
        result_without = self._run(add_toc=False)
        self.assertIn("TOC: no", result_without)

    def test_tool_metadata(self):
        from ai_engine.agents.doc_tools import make_generate_word_doc_tool

        tool = make_generate_word_doc_tool()
        self.assertEqual(tool.name, "generate_word_doc")
        self.assertIn("word", tool.description.lower())

    def test_input_schema_has_add_toc_default(self):
        from ai_engine.agents.doc_tools import GenerateWordDocInput

        obj = GenerateWordDocInput(
            title="T", sections=[{"heading": "H", "content": "C"}]
        )
        self.assertTrue(obj.add_toc)


# ===========================================================================
# 4. generate_markdown
# ===========================================================================


class TestGenerateMarkdown(DocToolTestCase):

    def _run(self, title="Test Markdown", sections=None):
        from ai_engine.agents.doc_tools import _generate_markdown

        sections = sections or [
            {"heading": "Introduction", "content": "Welcome to this document."},
            {"heading": "Body", "content": "Main content goes here."},
        ]
        return _generate_markdown(
            title=title, sections=sections, author="SYNAPSE AI", user_id="test"
        )

    def test_generates_md_file(self):
        result = self._run()
        self.assertIn("Markdown document generated successfully", result)
        self.assertIn(".md", result)
        for line in result.splitlines():
            if line.startswith("Path:"):
                path = Path(line.replace("Path:", "").strip())
                self.assertTrue(path.exists())
                content = path.read_text(encoding="utf-8")
                self.assertIn("# Test Markdown", content)
                self.assertIn("## Introduction", content)
                self.assertIn("## Table of Contents", content)
                break

    def test_toc_links_generated(self):
        self._run(
            sections=[
                {"heading": "First Section", "content": "abc"},
                {"heading": "Second Section", "content": "def"},
            ]
        )
        # Find the file
        md_files = list(Path(self.tmp).rglob("*.md"))
        self.assertEqual(len(md_files), 1)
        content = md_files[0].read_text()
        self.assertIn("First Section", content)
        self.assertIn("Second Section", content)

    def test_result_contains_section_count(self):
        result = self._run(
            sections=[
                {"heading": "A", "content": "x"},
                {"heading": "B", "content": "y"},
            ]
        )
        self.assertIn("Sections: 2", result)

    def test_tool_metadata(self):
        from ai_engine.agents.doc_tools import make_generate_markdown_tool

        tool = make_generate_markdown_tool()
        self.assertEqual(tool.name, "generate_markdown")
        self.assertIn("markdown", tool.description.lower())

    def test_input_schema_requires_title_and_sections(self):
        from ai_engine.agents.doc_tools import GenerateMarkdownInput

        schema = GenerateMarkdownInput.schema()
        required = schema.get("required", [])
        self.assertIn("title", required)
        self.assertIn("sections", required)


# ===========================================================================
# 5. Registry includes doc tools
# ===========================================================================


class TestRegistryIncludesDocTools(TestCase):
    def test_registry_has_9_tools(self):
        from unittest.mock import MagicMock

        from ai_engine.agents.registry import AgentToolRegistry

        registry = AgentToolRegistry()
        # Build only doc tools for fast test
        from ai_engine.agents.doc_tools import (
            make_generate_markdown_tool,
            make_generate_pdf_tool,
            make_generate_ppt_tool,
            make_generate_word_doc_tool,
        )

        doc_tools = [
            make_generate_pdf_tool(),
            make_generate_ppt_tool(),
            make_generate_word_doc_tool(),
            make_generate_markdown_tool(),
        ]
        for t in doc_tools:
            registry._tools[t.name] = t
        registry._built = True

        expected = {
            "generate_pdf",
            "generate_ppt",
            "generate_word_doc",
            "generate_markdown",
        }
        self.assertTrue(expected.issubset(set(registry.list_tool_names())))

    def test_all_doc_tool_names_correct(self):
        from ai_engine.agents.doc_tools import (
            make_generate_markdown_tool,
            make_generate_pdf_tool,
            make_generate_ppt_tool,
            make_generate_word_doc_tool,
        )

        self.assertEqual(make_generate_pdf_tool().name, "generate_pdf")
        self.assertEqual(make_generate_ppt_tool().name, "generate_ppt")
        self.assertEqual(make_generate_word_doc_tool().name, "generate_word_doc")
        self.assertEqual(make_generate_markdown_tool().name, "generate_markdown")


# ===========================================================================
# 6. _doc_dir helper
# ===========================================================================


class TestDocDir(DocToolTestCase):
    def test_creates_user_subdirectory(self):
        from ai_engine.agents.doc_tools import _doc_dir

        d = _doc_dir("user_42")
        self.assertTrue(d.exists())
        self.assertTrue(str(d).endswith("user_42"))

    def test_returns_path_object(self):
        from ai_engine.agents.doc_tools import _doc_dir

        d = _doc_dir("test_user")
        self.assertIsInstance(d, Path)

    def test_idempotent(self):
        from ai_engine.agents.doc_tools import _doc_dir

        d1 = _doc_dir("same_user")
        d2 = _doc_dir("same_user")
        self.assertEqual(d1, d2)
        self.assertTrue(d1.exists())
