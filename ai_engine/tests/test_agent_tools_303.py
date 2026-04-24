"""
Tests for TASK-303 — AI Agent Tool Expansion

Covers:
  - web_search: no-key fallback, result shape, domain filter pass-through
  - run_python_code: safe execution, stdout capture, timeout, security blocks
  - read_document: URL validation, PDF/text dispatch, error handling
  - generate_chart: bar/line/pie/scatter/histogram, base64 output, bad input
  - Registry: all 4 new tools registered
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# ── web_search ────────────────────────────────────────────────────────────────


class TestWebSearch:

    def test_no_tavily_key_returns_error(self):
        """Returns error dict when TAVILY_API_KEY not set."""
        from ai_engine.agents.tools import _web_search

        env = {k: v for k, v in os.environ.items() if k != "TAVILY_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            result = _web_search("AI news")

        assert isinstance(result, list)
        assert "error" in result[0]
        assert "TAVILY_API_KEY" in result[0]["error"]

    def test_returns_formatted_results(self):
        """Returns list of dicts with title, url, snippet, score."""
        from ai_engine.agents.tools import _web_search

        mock_client_instance = MagicMock()
        mock_client_instance.search.return_value = {
            "results": [
                {
                    "title": "AI News",
                    "url": "https://example.com",
                    "content": "AI is cool",
                    "score": 0.9,
                },
            ]
        }
        mock_tavily_mod = MagicMock()
        mock_tavily_mod.TavilyClient.return_value = mock_client_instance

        with (
            patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}),
            patch.dict("sys.modules", {"tavily": mock_tavily_mod}),
        ):
            result = _web_search("AI news", max_results=1)

        assert len(result) == 1
        assert result[0]["title"] == "AI News"
        assert result[0]["url"] == "https://example.com"
        assert "snippet" in result[0]
        assert "score" in result[0]

    def test_respects_max_results(self):
        """Passes max_results to Tavily client."""
        from ai_engine.agents.tools import _web_search

        mock_client_instance = MagicMock()
        mock_client_instance.search.return_value = {"results": []}
        mock_tavily_mod = MagicMock()
        mock_tavily_mod.TavilyClient.return_value = mock_client_instance

        with (
            patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}),
            patch.dict("sys.modules", {"tavily": mock_tavily_mod}),
        ):
            _web_search("test", max_results=7)

        call_kwargs = mock_client_instance.search.call_args[1]
        assert call_kwargs["max_results"] == 7

    def test_passes_include_domains(self):
        """Passes include_domains to Tavily client when provided."""
        from ai_engine.agents.tools import _web_search

        mock_client_instance = MagicMock()
        mock_client_instance.search.return_value = {"results": []}
        mock_tavily_mod = MagicMock()
        mock_tavily_mod.TavilyClient.return_value = mock_client_instance

        with (
            patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}),
            patch.dict("sys.modules", {"tavily": mock_tavily_mod}),
        ):
            _web_search("test", include_domains=["arxiv.org"])

        call_kwargs = mock_client_instance.search.call_args[1]
        assert call_kwargs["include_domains"] == ["arxiv.org"]

    def test_handles_api_error_gracefully(self):
        """Returns error dict on API failure."""
        from ai_engine.agents.tools import _web_search

        mock_client_instance = MagicMock()
        mock_client_instance.search.side_effect = Exception("API error")
        mock_tavily_mod = MagicMock()
        mock_tavily_mod.TavilyClient.return_value = mock_client_instance

        with (
            patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}),
            patch.dict("sys.modules", {"tavily": mock_tavily_mod}),
        ):
            result = _web_search("test")

        assert "error" in result[0]

    def test_tavily_not_installed_returns_error(self):
        """Returns error dict when tavily-python not installed."""
        from ai_engine.agents.tools import _web_search

        with (
            patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}),
            patch.dict("sys.modules", {"tavily": None}),
        ):
            result = _web_search("test")

        assert "error" in result[0]


# ── run_python_code ───────────────────────────────────────────────────────────


class TestRunPythonCode:

    def test_executes_simple_code(self):
        """Executes simple print statement and returns stdout."""
        from ai_engine.agents.tools import _run_python_code

        result = _run_python_code('print("hello")')
        assert result["success"] is True
        assert "hello" in result["stdout"]

    def test_captures_math_output(self):
        """Executes math module usage and captures result."""
        from ai_engine.agents.tools import _run_python_code

        result = _run_python_code("import math\nprint(math.sqrt(16))")
        assert result["success"] is True
        assert "4.0" in result["stdout"]

    def test_captures_error_in_stderr(self):
        """Captures exception traceback in stderr, success=False."""
        from ai_engine.agents.tools import _run_python_code

        result = _run_python_code('raise ValueError("test error")')
        assert result["success"] is False
        assert "ValueError" in result["stderr"]

    def test_blocks_open_builtin(self):
        """Blocks open() calls (filesystem access)."""
        from ai_engine.agents.tools import _run_python_code

        result = _run_python_code('open("/etc/passwd", "r")')
        assert result["success"] is False
        assert "SecurityError" in result["stderr"] or "not allowed" in result["stderr"]

    def test_blocks_subprocess(self):
        """Blocks subprocess import pattern."""
        from ai_engine.agents.tools import _run_python_code

        result = _run_python_code("import subprocess")
        assert result["success"] is False
        assert "SecurityError" in result["stderr"] or "not allowed" in result["stderr"]

    def test_blocks_os_system(self):
        """Blocks os.system pattern."""
        from ai_engine.agents.tools import _run_python_code

        result = _run_python_code('import os; os.system("ls")')
        assert result["success"] is False

    def test_timeout_respected(self):
        """Enforces timeout — infinite loop returns TimeoutError."""
        from ai_engine.agents.tools import _run_python_code

        result = _run_python_code("while True: pass", timeout_seconds=1)
        assert result["success"] is False
        assert "Timeout" in result["stderr"] or "timeout" in result["stderr"].lower()

    def test_statistics_module_allowed(self):
        """statistics module is accessible in the sandbox."""
        from ai_engine.agents.tools import _run_python_code

        result = _run_python_code(
            "import statistics\nprint(statistics.mean([1,2,3,4,5]))"
        )
        assert result["success"] is True
        assert "3" in result["stdout"]

    def test_json_module_allowed(self):
        """json module is accessible in the sandbox."""
        from ai_engine.agents.tools import _run_python_code

        result = _run_python_code('import json\nprint(json.dumps({"key": "value"}))')
        assert result["success"] is True
        assert '"key"' in result["stdout"]

    def test_stdout_capped_at_4000_chars(self):
        """Output is capped at 4000 characters."""
        from ai_engine.agents.tools import _run_python_code

        result = _run_python_code('print("x" * 10000)')
        assert len(result["stdout"]) <= 4000


# ── read_document ─────────────────────────────────────────────────────────────


def _make_stream_mock(
    content: bytes, content_type: str = "text/plain", content_length: int | None = None
) -> MagicMock:
    """
    Build a mock for httpx's streaming context manager.

    _read_document now uses client.stream("GET", url) as resp: / resp.iter_bytes()
    This helper wires up the mock chain correctly.
    """
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    headers: dict = {"content-type": content_type}
    if content_length is not None:
        headers["content-length"] = str(content_length)

    # headers dict-style access used by _read_document
    mock_resp.headers = headers

    # Split content into realistic chunks
    chunk_size = 65536
    chunks = [
        content[i : i + chunk_size] for i in range(0, max(len(content), 1), chunk_size)
    ]
    mock_resp.iter_bytes.return_value = iter(chunks)

    # Context manager protocol: `with client.stream(...) as resp:`
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _patch_stream_client(mock_resp: MagicMock):
    """Return a patch context that injects the streaming mock into httpx.Client."""
    inner_client = MagicMock()
    inner_client.stream.return_value = mock_resp

    outer_ctx = MagicMock()
    outer_ctx.__enter__ = MagicMock(return_value=inner_client)
    outer_ctx.__exit__ = MagicMock(return_value=False)

    return patch("ai_engine.agents.tools.httpx.Client", return_value=outer_ctx)


class TestReadDocument:

    def test_rejects_non_http_url(self):
        """Returns error for non-http/https URLs."""
        from ai_engine.agents.tools import _read_document

        result = _read_document("file:///etc/passwd")
        assert "error" in result
        assert "http" in result["error"].lower()

    def test_reads_plain_text(self):
        """Downloads and returns plain text content."""
        from ai_engine.agents.tools import _read_document

        content = b"Hello world, this is a plain text document."
        mock_resp = _make_stream_mock(content, content_type="text/plain")
        with _patch_stream_client(mock_resp):
            result = _read_document("https://example.com/doc.txt")

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "Hello world" in result["text"]
        assert result["doc_type"] == "text"

    def test_returns_error_on_fetch_failure(self):
        """Returns error dict when HTTP request fails."""
        import httpx as _httpx

        from ai_engine.agents.tools import _read_document

        inner_client = MagicMock()
        inner_client.stream.side_effect = _httpx.RequestError(
            "connection failed", request=None
        )
        outer_ctx = MagicMock()
        outer_ctx.__enter__ = MagicMock(return_value=inner_client)
        outer_ctx.__exit__ = MagicMock(return_value=False)

        with patch("ai_engine.agents.tools.httpx.Client", return_value=outer_ctx):
            result = _read_document("https://unreachable.example.com/doc.pdf")

        assert "error" in result

    def test_truncates_to_max_chars(self):
        """Truncates text to max_chars."""
        from ai_engine.agents.tools import _read_document

        long_content = b"A" * 20000
        mock_resp = _make_stream_mock(long_content, content_type="text/plain")
        with _patch_stream_client(mock_resp):
            result = _read_document("https://example.com/long.txt", max_chars=5000)

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert len(result["text"]) <= 5000
        assert result["truncated"] is True

    def test_blocks_oversized_content_length_header(self):
        """SEC-07: Rejects file when Content-Length header exceeds the download limit."""
        from ai_engine.agents.tools import _MAX_DOWNLOAD_BYTES, _read_document

        oversized = _MAX_DOWNLOAD_BYTES + 1
        mock_resp = _make_stream_mock(
            b"", content_type="text/plain", content_length=oversized
        )
        with _patch_stream_client(mock_resp):
            result = _read_document("https://example.com/huge.bin")

        assert "error" in result
        assert "large" in result["error"].lower() or "limit" in result["error"].lower()

    def test_blocks_oversized_streaming_body(self):
        """SEC-07: Rejects download when streamed bytes exceed limit (no Content-Length)."""
        from ai_engine.agents.tools import _MAX_DOWNLOAD_BYTES, _read_document

        # One chunk bigger than the limit — no Content-Length header
        huge_chunk = b"X" * (_MAX_DOWNLOAD_BYTES + 1)
        mock_resp = _make_stream_mock(huge_chunk, content_type="text/plain")
        with _patch_stream_client(mock_resp):
            result = _read_document("https://example.com/huge_no_cl.bin")

        assert "error" in result
        assert "large" in result["error"].lower() or "limit" in result["error"].lower()


# ── generate_chart ────────────────────────────────────────────────────────────


class TestGenerateChart:

    def _check_base64_png(self, result: dict):
        """Assert result has valid base64 PNG structure."""
        assert result.get("success") is True
        assert "base64_png" in result
        assert "data_uri" in result
        assert result["data_uri"].startswith("data:image/png;base64,")
        # Verify it's valid base64
        import base64

        decoded = base64.b64decode(result["base64_png"])
        assert decoded[:4] == b"\x89PNG"  # PNG magic bytes

    def test_bar_chart(self):
        """Generates a valid bar chart PNG."""
        from ai_engine.agents.tools import _generate_chart

        result = _generate_chart(
            chart_type="bar",
            labels=["A", "B", "C"],
            values=[10.0, 20.0, 15.0],
            title="Test Bar Chart",
        )
        self._check_base64_png(result)

    def test_line_chart(self):
        """Generates a valid line chart PNG."""
        from ai_engine.agents.tools import _generate_chart

        result = _generate_chart(
            chart_type="line",
            labels=["Q1", "Q2", "Q3", "Q4"],
            values=[100.0, 120.0, 110.0, 140.0],
            title="Quarterly Revenue",
            y_label="Revenue ($)",
        )
        self._check_base64_png(result)

    def test_pie_chart(self):
        """Generates a valid pie chart PNG."""
        from ai_engine.agents.tools import _generate_chart

        result = _generate_chart(
            chart_type="pie",
            labels=["AI", "ML", "DL"],
            values=[40.0, 35.0, 25.0],
        )
        self._check_base64_png(result)

    def test_scatter_chart(self):
        """Generates a valid scatter chart PNG."""
        from ai_engine.agents.tools import _generate_chart

        result = _generate_chart(
            chart_type="scatter",
            labels=["1", "2", "3", "4"],
            values=[1.0, 4.0, 9.0, 16.0],
        )
        self._check_base64_png(result)

    def test_histogram(self):
        """Generates a valid histogram PNG."""
        from ai_engine.agents.tools import _generate_chart

        result = _generate_chart(
            chart_type="histogram",
            labels=["x"],
            values=[1.0, 2.0, 2.0, 3.0, 3.0, 3.0, 4.0, 5.0],
        )
        self._check_base64_png(result)

    def test_unknown_chart_type_returns_error(self):
        """Returns error for unknown chart type."""
        from ai_engine.agents.tools import _generate_chart

        result = _generate_chart(
            chart_type="radar",
            labels=["A", "B"],
            values=[1.0, 2.0],
        )
        assert "error" in result

    def test_mismatched_labels_values_returns_error(self):
        """Returns error when labels and values have different lengths."""
        from ai_engine.agents.tools import _generate_chart

        result = _generate_chart(
            chart_type="bar",
            labels=["A", "B", "C"],
            values=[1.0, 2.0],  # only 2 values for 3 labels
        )
        assert "error" in result

    def test_empty_labels_returns_error(self):
        """Returns error for empty labels list."""
        from ai_engine.agents.tools import _generate_chart

        result = _generate_chart(
            chart_type="bar",
            labels=[],
            values=[],
        )
        assert "error" in result

    def test_data_uri_format(self):
        """data_uri is valid data URI for browser embedding."""
        from ai_engine.agents.tools import _generate_chart

        result = _generate_chart(
            chart_type="bar",
            labels=["X", "Y"],
            values=[5.0, 10.0],
        )
        assert result["data_uri"].startswith("data:image/png;base64,")


# ── Registry integration ──────────────────────────────────────────────────────


class TestRegistryTask303:

    def test_new_tools_registered(self):
        """All 4 TASK-303 tools are importable and buildable from the tools module."""
        from ai_engine.agents.tools import (
            make_generate_chart_tool,
            make_read_document_tool,
            make_run_python_tool,
            make_web_search_tool,
        )

        for factory in [
            make_web_search_tool,
            make_run_python_tool,
            make_read_document_tool,
            make_generate_chart_tool,
        ]:
            tool = factory()
            assert tool is not None
            assert tool.name  # non-empty name

    def test_tool_descriptions_non_empty(self):
        """Each new tool has a non-empty description."""
        from ai_engine.agents.tools import (
            make_generate_chart_tool,
            make_read_document_tool,
            make_run_python_tool,
            make_web_search_tool,
        )

        for factory in [
            make_web_search_tool,
            make_run_python_tool,
            make_read_document_tool,
            make_generate_chart_tool,
        ]:
            tool = factory()
            assert tool.description, f"{tool.name} has empty description"
            assert len(tool.description) > 20, f"{tool.name} description too short"
