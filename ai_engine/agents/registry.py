"""
ai_engine.agents.registry
~~~~~~~~~~~~~~~~~~~~~~~~~
Centralized tool registration system for SYNAPSE agents.

Tools are registered with LangChain's StructuredTool interface, which
gives the ReAct agent a clean name + description + typed input schema
for every capability it can invoke.

Phase 5.1 — Agent Framework (Week 13)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from langchain_core.tools import BaseTool, StructuredTool

logger = logging.getLogger(__name__)

# Module-level singleton
_registry_instance: Optional["AgentToolRegistry"] = None


class AgentToolRegistry:
    """
    Central registry that holds all available LangChain tools.

    Tools are imported lazily from ai_engine.agents.tools so that
    heavy imports (sentence-transformers, psycopg2, etc.) are only
    triggered when the registry is first built.

    Usage::

        registry = get_registry()
        tools = registry.get_tools()            # all registered tools
        tools = registry.get_tools(["search_knowledge_base", "fetch_articles"])
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._built = False

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> "AgentToolRegistry":
        """Import and register all Phase-5.1 tools. Called once lazily."""
        if self._built:
            return self

        from ai_engine.agents.doc_tools import (
            make_generate_markdown_tool,
            make_generate_pdf_tool,
            make_generate_ppt_tool,
            make_generate_word_doc_tool,
        )
        from ai_engine.agents.project_tools import make_create_project_tool
        from ai_engine.agents.tools import (  # TASK-303: new expanded tools
            make_analyze_trends_tool,
            make_fetch_articles_tool,
            make_fetch_arxiv_papers_tool,
            make_generate_chart_tool,
            make_read_document_tool,
            make_run_python_tool,
            make_search_github_tool,
            make_search_knowledge_base_tool,
            make_web_search_tool,
        )

        tool_factories = [
            # Phase 5.1 — research & analysis tools
            make_search_knowledge_base_tool,
            make_fetch_articles_tool,
            make_analyze_trends_tool,
            make_search_github_tool,
            make_fetch_arxiv_papers_tool,
            # TASK-303 — expanded tools
            make_web_search_tool,  # live web search via Tavily
            make_run_python_tool,  # Python code execution sandbox
            make_read_document_tool,  # PDF/document reader
            make_generate_chart_tool,  # chart generator (bar, line, pie, scatter)
            # Phase 5.2 — document generation tools
            make_generate_pdf_tool,
            make_generate_ppt_tool,
            make_generate_word_doc_tool,
            make_generate_markdown_tool,
            # Phase 5.3 — project builder tool
            make_create_project_tool,
        ]

        for factory in tool_factories:
            try:
                tool: BaseTool = factory()
                self._tools[tool.name] = tool
                logger.info("Registered agent tool: %s", tool.name)
            except Exception as exc:
                logger.error(
                    "Failed to register tool from %s: %s", factory.__name__, exc
                )

        self._built = True
        logger.info(
            "AgentToolRegistry built with %d tools: %s",
            len(self._tools),
            list(self._tools.keys()),
        )
        return self

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_tools(self, names: Optional[List[str]] = None) -> List[BaseTool]:
        """
        Return a list of tools.

        Args:
            names: Optional list of tool names to filter. If None, returns all.

        Returns:
            List of BaseTool instances ready for use in an AgentExecutor.
        """
        if not self._built:
            self.build()

        if names is None:
            return list(self._tools.values())

        result = []
        for name in names:
            tool = self._tools.get(name)
            if tool:
                result.append(tool)
            else:
                logger.warning(
                    "Tool '%s' not found in registry. Available: %s",
                    name,
                    list(self._tools.keys()),
                )
        return result

    def register(self, tool: BaseTool) -> None:
        """Register a custom tool at runtime."""
        self._tools[tool.name] = tool
        logger.info("Dynamically registered tool: %s", tool.name)

    def list_tool_names(self) -> List[str]:
        """Return names of all registered tools."""
        if not self._built:
            self.build()
        return list(self._tools.keys())

    def describe(self) -> List[Dict[str, str]]:
        """Return name + description for every registered tool (for API responses)."""
        if not self._built:
            self.build()
        return [
            {"name": t.name, "description": t.description} for t in self._tools.values()
        ]

    def __len__(self) -> int:
        if not self._built:
            self.build()
        return len(self._tools)

    def __repr__(self) -> str:
        return f"AgentToolRegistry(tools={self.list_tool_names()})"


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------


def get_registry() -> AgentToolRegistry:
    """Return the module-level AgentToolRegistry singleton (built on first call)."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentToolRegistry()
    return _registry_instance
