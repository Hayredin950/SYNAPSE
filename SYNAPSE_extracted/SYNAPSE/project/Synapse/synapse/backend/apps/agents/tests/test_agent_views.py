"""
Unit tests for ai_engine agent executor, registry, and base class.
No DB access required — pure unit tests.

Phase 5.1 — Agent Framework (Week 13)
"""

import os
import sys

# Ensure repo root is on path so ai_engine can be imported
_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.tools import StructuredTool

# ---------------------------------------------------------------------------
# AgentToolRegistry tests
# ---------------------------------------------------------------------------


class TestAgentToolRegistry:

    def _fresh_registry(self):
        from ai_engine.agents.registry import AgentToolRegistry

        r = AgentToolRegistry()
        r._built = True
        r._tools = {}
        return r

    def test_registry_builds_and_lists_tools(self):
        from ai_engine.agents.registry import AgentToolRegistry

        r = AgentToolRegistry()
        mock_tool = MagicMock(spec=StructuredTool)
        mock_tool.name = "mock_tool"
        mock_tool.description = "A mock tool"
        r._built = True
        r._tools = {"mock_tool": mock_tool}
        assert "mock_tool" in r.list_tool_names()

    def test_registry_get_tools_all(self):
        r = self._fresh_registry()
        tool_a = MagicMock(spec=StructuredTool)
        tool_a.name = "tool_a"
        tool_b = MagicMock(spec=StructuredTool)
        tool_b.name = "tool_b"
        r._tools = {"tool_a": tool_a, "tool_b": tool_b}
        assert len(r.get_tools()) == 2

    def test_registry_get_tools_filtered(self):
        r = self._fresh_registry()
        tool_a = MagicMock(spec=StructuredTool)
        tool_a.name = "tool_a"
        tool_b = MagicMock(spec=StructuredTool)
        tool_b.name = "tool_b"
        r._tools = {"tool_a": tool_a, "tool_b": tool_b}
        tools = r.get_tools(["tool_a"])
        assert len(tools) == 1
        assert tools[0].name == "tool_a"

    def test_registry_get_tools_missing_name_warns(self):
        r = self._fresh_registry()
        tools = r.get_tools(["nonexistent"])
        assert tools == []

    def test_registry_register_custom_tool(self):
        r = self._fresh_registry()
        custom = MagicMock(spec=StructuredTool)
        custom.name = "my_custom_tool"
        r.register(custom)
        assert "my_custom_tool" in r._tools

    def test_registry_describe(self):
        r = self._fresh_registry()
        tool = MagicMock(spec=StructuredTool)
        tool.name = "search_knowledge_base"
        tool.description = "Search the knowledge base."
        r._tools = {"search_knowledge_base": tool}
        desc = r.describe()
        assert len(desc) == 1
        assert desc[0]["name"] == "search_knowledge_base"
        assert desc[0]["description"] == "Search the knowledge base."

    def test_registry_len(self):
        r = self._fresh_registry()
        r._tools = {"a": MagicMock(), "b": MagicMock(), "c": MagicMock()}
        assert len(r) == 3

    def test_get_registry_singleton(self):
        from ai_engine.agents.registry import get_registry

        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2


# ---------------------------------------------------------------------------
# SynapseAgentExecutor tests
# ---------------------------------------------------------------------------


class TestSynapseAgentExecutor:

    def _make_executor(self):
        from ai_engine.agents.executor import SynapseAgentExecutor
        from ai_engine.agents.registry import AgentToolRegistry

        registry = AgentToolRegistry()
        registry._built = True
        registry._tools = {}
        return SynapseAgentExecutor(registry=registry)

    def test_executor_list_tools_empty(self):
        executor = self._make_executor()
        assert executor.list_tools() == []

    def test_executor_health_returns_dict(self):
        executor = self._make_executor()
        health = executor.health()
        assert health["status"] == "ok"
        assert "tools_registered" in health
        assert "tool_names" in health
        assert "model" in health
        assert "max_iterations" in health
        assert "max_execution_time_s" in health

    def test_executor_health_tool_count(self):
        from ai_engine.agents.executor import SynapseAgentExecutor
        from ai_engine.agents.registry import AgentToolRegistry

        registry = AgentToolRegistry()
        registry._built = True
        t1 = MagicMock()
        t1.name = "t1"
        t1.description = "d1"
        t2 = MagicMock()
        t2.name = "t2"
        t2.description = "d2"
        registry._tools = {"t1": t1, "t2": t2}
        executor = SynapseAgentExecutor(registry=registry)
        assert executor.health()["tools_registered"] == 2

    def test_executor_run_delegates_to_agent(self):
        executor = self._make_executor()
        expected = {
            "answer": "42",
            "intermediate_steps": [],
            "tokens_used": 100,
            "cost_usd": 0.0,
            "execution_time_s": 1.0,
            "success": True,
            "error": None,
        }
        mock_agent = MagicMock()
        mock_agent.run.return_value = expected
        executor._default_agent = mock_agent
        result = executor.run("What is the answer?")
        assert result["answer"] == "42"
        assert result["success"] is True
        mock_agent.run.assert_called_once_with(
            "What is the answer?", extra_context=None
        )

    def test_get_executor_singleton(self):
        from ai_engine.agents.executor import get_executor

        e1 = get_executor()
        e2 = get_executor()
        assert e1 is e2


# ---------------------------------------------------------------------------
# SynapseAgent base — static method tests (no LLM calls)
# ---------------------------------------------------------------------------


class TestSynapseAgentBase:

    def test_estimate_tokens(self):
        from ai_engine.agents.base import SynapseAgent

        tokens = SynapseAgent._estimate_tokens("hello world", "response text here")
        assert tokens >= 1

    def test_estimate_cost(self):
        from ai_engine.agents.base import SynapseAgent

        cost = SynapseAgent._estimate_cost(1_000_000)
        # 1M tokens @ $0.075/1M = 0.075
        assert abs(cost - 0.075) < 0.001

    def test_estimate_cost_zero_tokens(self):
        from ai_engine.agents.base import SynapseAgent

        assert SynapseAgent._estimate_cost(0) == 0.0

    def test_agent_constants(self):
        from ai_engine.agents.base import SynapseAgent

        assert SynapseAgent.MAX_ITERATIONS == 10
        assert SynapseAgent.MAX_EXECUTION_TIME == 300
        assert SynapseAgent.MAX_TOKENS_PER_TASK == 10_000
