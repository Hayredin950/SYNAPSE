"""
ai_engine.agents.base
~~~~~~~~~~~~~~~~~~~~~
LangChain / LangGraph ReAct Agent base class for SYNAPSE.

The ReAct (Reasoning + Acting) pattern drives every SYNAPSE agent:
  1. Thought  — reason about the current state and available tools
  2. Action   — select a tool and its input parameters
  3. Observation — receive the tool result
  4. Repeat   — iterate until goal is reached or limits exceeded

Safety limits (from 13_AI_Agent_Spec.tex):
  - max_iterations : 10  (ReAct loop cycles)
  - max_execution_time : 300 seconds
  - max_tokens : 10 000 per task
  - token cost logging per run

Uses LangGraph's create_react_agent (LangChain ≥ 0.3 / LangGraph ≥ 0.2).

Phase 5.1 — Agent Framework (Week 13)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool

# langchain_openai and langgraph are imported lazily inside methods so that
# doc_tools.py (which only uses reportlab/pptx) can be imported without
# requiring langchain_openai to be installed in environments that only use
# the document generation tools.
try:
    from langchain_openai import ChatOpenAI as _ChatOpenAI  # type: ignore

    _OPENAI_AVAILABLE = True
except ImportError:
    _ChatOpenAI = None  # type: ignore
    _OPENAI_AVAILABLE = False

try:
    from langgraph.prebuilt import (
        create_react_agent as _create_react_agent,  # type: ignore
    )

    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _create_react_agent = None  # type: ignore
    _LANGGRAPH_AVAILABLE = False

# TASK-302: Anthropic Claude
try:
    from langchain_anthropic import ChatAnthropic as _ChatAnthropic  # type: ignore

    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ChatAnthropic = None  # type: ignore
    _ANTHROPIC_AVAILABLE = False

# TASK-302: Ollama local LLMs
try:
    from langchain_ollama import ChatOllama as _ChatOllama  # type: ignore

    _OLLAMA_AVAILABLE = True
except ImportError:
    _ChatOllama = None  # type: ignore
    _OLLAMA_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — grounding and safety rules for the SYNAPSE ReAct agent
# ---------------------------------------------------------------------------

REACT_SYSTEM_PROMPT = (
    "You are SYNAPSE Agent, an intelligent AI assistant that autonomously completes tasks "
    "for the user WITHOUT asking for clarification or additional input. "
    "You must ALWAYS produce a complete result using your tools and your own knowledge.\n\n"
    "CRITICAL RULES:\n"
    "1. NEVER ask the user for more information — complete the task with what you have.\n"
    "2. For document/report generation: call the appropriate tool (generate_pdf, generate_ppt, "
    "   generate_word_doc, generate_markdown) immediately with content YOU generate from your knowledge. "
    "   Create realistic, informative section content yourself — do not wait for user input.\n"
    "3. For research tasks: use 1-3 tool calls maximum, then synthesize a clear answer.\n"
    "4. For trend analysis: call analyze_trends once, then summarize the result.\n"
    "5. For GitHub searches: call search_github once with a good query, then present results.\n"
    "6. For arXiv: call fetch_arxiv_papers once; if rate-limited, state so and use your knowledge.\n"
    "7. For project scaffolding: call create_project immediately with the requested type and name.\n"
    "8. If a tool fails, use your built-in knowledge to answer instead.\n"
    "9. Be concise, accurate, and always produce a final answer.\n"
    "10. Cite sources when available.\n"
)


# ---------------------------------------------------------------------------
# SynapseAgent
# ---------------------------------------------------------------------------


class SynapseAgent:
    """
    ReAct agent built on LangGraph's create_react_agent.

    Usage::

        from ai_engine.agents import get_executor
        executor = get_executor()
        result = executor.run("Summarise the latest AI trends from the knowledge base")
    """

    # Safety defaults (from 13_AI_Agent_Spec.tex)
    MAX_ITERATIONS: int = 10
    MAX_EXECUTION_TIME: int = 300  # seconds
    MAX_TOKENS_PER_TASK: int = 10_000

    def __init__(
        self,
        tools: List[BaseTool],
        model_name: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        max_iterations: int = MAX_ITERATIONS,
        max_execution_time: int = MAX_EXECUTION_TIME,
        verbose: bool = True,
        scitely_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        # TASK-302: multi-provider support
        provider: str = "auto",  # "auto"|"openai"|"anthropic"|"ollama"|"gemini"|"scitely"
        anthropic_api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
    ) -> None:
        self.tools = tools
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.max_execution_time = max_execution_time
        self.verbose = verbose
        self.provider = provider
        # Per-user API key overrides (take priority over env vars)
        self._scitely_api_key = scitely_api_key
        self._openrouter_api_key = openrouter_api_key
        self._gemini_api_key = gemini_api_key
        self._anthropic_api_key = anthropic_api_key
        self._ollama_base_url = ollama_base_url

        self._llm = self._build_llm()
        self._graph = None  # LangGraph compiled graph — built lazily

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_llm(self):
        """
        Instantiate the LLM used by the agent.

        QA-24: Delegates to the shared ai_engine.agents.llm_factory.build_llm()
        to avoid duplicating provider-routing logic. Per-user API key overrides
        are passed through; see llm_factory.py for the full provider selection order.

        Provider selection order (TASK-302):
          1. provider="anthropic"  → Claude (ANTHROPIC_API_KEY required)
          2. provider="ollama"     → local Ollama (OLLAMA_BASE_URL, no API key)
          3. provider="gemini"     → Google Gemini (GEMINI_API_KEY required)
          4. provider="scitely"    → Scitely (SCITELY_API_KEY; OpenAI-compatible)
          5. provider="openai"     → OpenRouter-compatible endpoint
          6. provider="auto"       → tries Scitely → OpenRouter → Gemini → raises
        """
        from ai_engine.agents.llm_factory import build_llm

        return build_llm(
            provider=self.provider,
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            scitely_api_key=self._scitely_api_key,
            openrouter_api_key=self._openrouter_api_key,
            gemini_api_key=self._gemini_api_key,
            anthropic_api_key=self._anthropic_api_key,
            ollama_base_url=self._ollama_base_url,
        )

    @property
    def graph(self):
        """Lazy-initialised LangGraph ReAct graph (built once, reused)."""
        if self._graph is None:
            if not _LANGGRAPH_AVAILABLE or _create_react_agent is None:
                raise ImportError(
                    "langgraph is not installed. Install it with: pip install langgraph"
                )
            self._graph = _create_react_agent(
                model=self._llm,
                tools=self.tools,
                prompt=REACT_SYSTEM_PROMPT,
            )
        return self._graph

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        task: str,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an agent task synchronously.

        Returns a dict with:
          - answer            : str — the final answer produced by the agent
          - intermediate_steps: list — all tool call records
          - tokens_used       : int — estimated token count
          - cost_usd          : float — estimated cost in USD
          - execution_time_s  : float — wall-clock seconds
          - success           : bool
          - error             : str | None
        """
        start = time.time()
        result: Dict[str, Any] = {
            "answer": "",
            "intermediate_steps": [],
            "tokens_used": 0,
            "cost_usd": 0.0,
            "execution_time_s": 0.0,
            "success": False,
            "error": None,
        }

        try:
            config = {"recursion_limit": self.max_iterations * 2 + 2}

            # Augment the task prompt with extra context if provided
            augmented_task = task
            if extra_context:
                ctx_lines = [f"[{k}]: {v}" for k, v in extra_context.items() if v]
                if ctx_lines:
                    ctx_block = "\n".join(ctx_lines)
                    augmented_task = f"=== USER CONTEXT ===\n{ctx_block}\n=== END CONTEXT ===\n\n{task}"

            state = self.graph.invoke(
                {"messages": [HumanMessage(content=augmented_task)]},
                config=config,
            )
            messages = state.get("messages", [])
            answer = ""
            steps = []
            
            # Temporary storage for tool call details from AIMessage
            pending_tool_calls = {}

            for msg in messages:
                if isinstance(msg, AIMessage):
                    if msg.content:
                        answer = (
                            msg.content
                            if isinstance(msg.content, str)
                            else str(msg.content)
                        )
                    # If this message has tool calls, store them to match with subsequent ToolMessages
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            pending_tool_calls[tc["id"]] = {
                                "tool": tc["name"],
                                "tool_input": tc["args"],
                                "thought": msg.additional_kwargs.get("thought", "")
                            }
                elif isinstance(msg, ToolMessage):
                    # Match this observation with the tool call details
                    tc_id = getattr(msg, "tool_call_id", None)
                    tc_info = pending_tool_calls.get(tc_id, {})
                    
                    steps.append(
                        {
                            "tool": tc_info.get("tool") or getattr(msg, "name", "tool"),
                            "tool_input": tc_info.get("tool_input", ""),
                            "observation": str(msg.content)[:2000],
                            "thought": tc_info.get("thought", ""),
                        }
                    )

            result["answer"] = answer
            result["intermediate_steps"] = steps
            result["tokens_used"] = self._estimate_tokens(task, answer)
            result["cost_usd"] = self._estimate_cost(result["tokens_used"])
            result["success"] = True

        except Exception as exc:
            logger.exception("Agent task failed: %s", exc)
            result["error"] = str(exc)
            result["success"] = False

        finally:
            result["execution_time_s"] = round(time.time() - start, 3)

        return result

    def stream(
        self,
        task: str,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Stream intermediate steps and the final answer as they are produced.

        Yields dicts of the form:
          {"step": {"tool": ..., "observation": ...}}
          {"final": {"answer": ..., "tokens_used": ..., "cost_usd": ..., "execution_time_s": ...}}
          {"error": str}
        """
        start = time.time()
        try:
            config = {"recursion_limit": self.max_iterations * 2 + 2}
            for chunk in self.graph.stream(
                {"messages": [HumanMessage(content=task)]},
                config=config,
                stream_mode="updates",
            ):
                for node_name, node_output in chunk.items():
                    msgs = node_output.get("messages", [])
                    for msg in msgs:
                        if isinstance(msg, ToolMessage):
                            yield {
                                "step": {
                                    "tool": getattr(msg, "name", "tool"),
                                    "observation": str(msg.content)[:2000],
                                }
                            }
                        elif isinstance(msg, AIMessage) and msg.content:
                            answer = (
                                msg.content
                                if isinstance(msg.content, str)
                                else str(msg.content)
                            )
                            tokens = self._estimate_tokens(task, answer)
                            yield {
                                "final": {
                                    "answer": answer,
                                    "tokens_used": tokens,
                                    "cost_usd": self._estimate_cost(tokens),
                                    "execution_time_s": round(time.time() - start, 3),
                                }
                            }
        except Exception as exc:
            logger.exception("Agent stream failed: %s", exc)
            yield {"error": str(exc)}

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_steps(steps: list) -> List[Dict[str, Any]]:
        """Convert raw step records to JSON-serialisable dicts."""
        serialized = []
        for action, observation in steps:
            serialized.append(
                {
                    "thought": getattr(action, "log", ""),
                    "tool": getattr(action, "tool", ""),
                    "tool_input": getattr(action, "tool_input", ""),
                    "observation": str(observation)[:2000],
                }
            )
        return serialized

    @staticmethod
    def _estimate_tokens(prompt: str, response: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return max(1, (len(prompt) + len(response)) // 4)

    @staticmethod
    def _estimate_cost(tokens: int) -> float:
        """
        Estimate USD cost.
        Gemini 1.5 Flash: ~$0.075 per 1M tokens (blended approximation).
        """
        return round(tokens * 0.000_000_075, 8)
