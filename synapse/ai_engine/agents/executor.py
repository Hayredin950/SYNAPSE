"""
ai_engine.agents.executor
~~~~~~~~~~~~~~~~~~~~~~~~~
High-level SynapseAgentExecutor — combines the tool registry with the
ReAct agent base class and exposes a single-entry-point API used by the
Celery task and the FastAPI AI service.

Phase 5.1 — Agent Framework (Week 13)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

from .base import SynapseAgent  # noqa: F401 — SynapseAgent uses LangGraph internally
from .registry import AgentToolRegistry, get_registry

logger = logging.getLogger(__name__)

# Module-level singleton
_executor_instance: Optional["SynapseAgentExecutor"] = None


class SynapseAgentExecutor:
    """
    Orchestrates the full agent lifecycle:

      1. Resolves which tools to use (via AgentToolRegistry)
      2. Instantiates a SynapseAgent with those tools
      3. Runs or streams the task and returns structured results

    The executor caches a default agent (all tools) but can create
    task-specific agents on-the-fly with a restricted tool subset.

    Usage::

        executor = get_executor()

        # Synchronous
        result = executor.run("What are the trending AI papers this week?")

        # Streaming
        for event in executor.stream("Analyze trends for Python and Rust"):
            print(event)
    """

    def __init__(
        self,
        registry: Optional[AgentToolRegistry] = None,
        model_name: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        max_iterations: int = 10,
        max_execution_time: int = 300,
        verbose: bool = True,
        scitely_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ) -> None:
        self.registry = registry if registry is not None else get_registry()
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.max_execution_time = max_execution_time
        self.verbose = verbose
        # Per-user API key overrides
        self.scitely_api_key = scitely_api_key
        self.openrouter_api_key = openrouter_api_key
        self.gemini_api_key = gemini_api_key

        self._default_agent: Optional[SynapseAgent] = None

    # ------------------------------------------------------------------
    # Agent construction
    # ------------------------------------------------------------------

    def _get_default_agent(self) -> SynapseAgent:
        """Return (and lazily initialise) the default agent with all tools.
        Note: default agent is NOT cached when per-user keys are set, to avoid
        leaking one user's key into another user's session.
        """
        if self.scitely_api_key or self.openrouter_api_key or self.gemini_api_key:
            # Per-user keys — always build a fresh agent (no caching)
            tools = self.registry.get_tools()
            return SynapseAgent(
                tools=tools,
                model_name=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                max_iterations=self.max_iterations,
                max_execution_time=self.max_execution_time,
                verbose=self.verbose,
                scitely_api_key=self.scitely_api_key,
                openrouter_api_key=self.openrouter_api_key,
                gemini_api_key=self.gemini_api_key,
            )
        if self._default_agent is None:
            tools = self.registry.get_tools()
            self._default_agent = SynapseAgent(
                tools=tools,
                model_name=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                max_iterations=self.max_iterations,
                max_execution_time=self.max_execution_time,
                verbose=self.verbose,
            )
        return self._default_agent

    def _make_agent(self, tool_names: Optional[List[str]] = None) -> SynapseAgent:
        """Create a fresh agent, optionally restricted to specific tools."""
        if tool_names is None:
            return self._get_default_agent()

        tools = self.registry.get_tools(tool_names)
        if not tools:
            logger.warning(
                "No tools resolved for %s — falling back to all tools", tool_names
            )
            tools = self.registry.get_tools()

        return SynapseAgent(
            tools=tools,
            model_name=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            max_iterations=self.max_iterations,
            max_execution_time=self.max_execution_time,
            verbose=self.verbose,
            openrouter_api_key=self.openrouter_api_key,
            gemini_api_key=self.gemini_api_key,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a text string using tiktoken.
        Falls back to character/4 heuristic if tiktoken not installed.

        TASK-004-B3
        """
        try:
            import tiktoken  # type: ignore

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            return max(1, len(text) // 4)
        except Exception:
            return max(1, len(text) // 4)

    def _estimate_cost_usd(self, tokens: int) -> float:
        """Estimate cost in USD at $0.003/1K tokens (blended GPT-4o rate)."""
        return (tokens / 1000) * 0.003

    def check_budget_before_run(
        self,
        task: str,
        user_id: Optional[str] = None,
        role: str = "user",
    ) -> Dict[str, Any]:
        """
        Estimate token cost and check against daily budget before running.
        Returns dict with estimated_tokens, estimated_cost_usd, can_run, budget_status.

        TASK-004-B3
        """
        estimated_tokens = self._estimate_tokens(task)
        estimated_cost_usd = self._estimate_cost_usd(estimated_tokens)

        budget_status: Dict[str, Any] = {}
        can_run = True

        if user_id:
            try:
                from ai_engine.middleware.rate_limit import (
                    check_budget,
                    get_budget_status,
                )

                check_budget(user_id, role)  # raises BudgetExceededError if over limit
                budget_status = get_budget_status(user_id, role)
            except Exception as exc:
                from ai_engine.middleware.rate_limit import BudgetExceededError

                if isinstance(exc, BudgetExceededError):
                    can_run = False
                    budget_status = {
                        "error": str(exc),
                        "reset_at": exc.reset_at,
                    }

        return {
            "estimated_tokens": estimated_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "can_run": can_run,
            "budget_status": budget_status,
        }

    def run(
        self,
        task: str,
        tool_names: Optional[List[str]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        role: str = "user",
        timeout_seconds: int = 60,
    ) -> Dict[str, Any]:
        """
        Execute a task synchronously with budget check and timeout.

        Args:
            task:            Natural-language task description.
            tool_names:      Optional list of tool names to restrict the agent to.
            extra_context:   Additional key-value pairs injected into the agent prompt.
            user_id:         Optional user ID for budget tracking.
            role:            User plan role for budget/rate limits.
            timeout_seconds: Hard timeout for agent execution (default 60s).

        Returns:
            Dict with keys: answer, intermediate_steps, tokens_used,
                            cost_usd, execution_time_s, success, error,
                            estimated_tokens, estimated_cost_usd.
        """
        import concurrent.futures
        import functools

        # Pre-run token estimation
        estimated_tokens = self._estimate_tokens(task)
        estimated_cost_usd = self._estimate_cost_usd(estimated_tokens)

        agent = self._make_agent(tool_names)
        logger.info(
            "Running agent task (tools=%s, est_tokens=%d, est_cost=$%.4f): %s",
            tool_names or "all",
            estimated_tokens,
            estimated_cost_usd,
            task[:120],
        )

        # Execute with timeout using a thread (executor.run is sync)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    functools.partial(agent.run, task, extra_context=extra_context)
                )
                try:
                    result = future.result(timeout=timeout_seconds)
                except concurrent.futures.TimeoutError:
                    logger.error(
                        "agent_task_timeout user=%s timeout=%ds task='%.80s'",
                        user_id,
                        timeout_seconds,
                        task,
                    )
                    return {
                        "success": False,
                        "error": f"Query took too long (>{timeout_seconds}s). Try a simpler question.",
                        "answer": "",
                        "tokens_used": 0,
                        "cost_usd": 0.0,
                        "execution_time_s": timeout_seconds,
                        "estimated_tokens": estimated_tokens,
                        "estimated_cost_usd": estimated_cost_usd,
                    }
        except Exception as exc:
            logger.error("agent_run_exception: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "answer": "",
                "tokens_used": 0,
                "cost_usd": 0.0,
                "execution_time_s": 0.0,
                "estimated_tokens": estimated_tokens,
                "estimated_cost_usd": estimated_cost_usd,
            }

        # Record actual token usage for budget tracking
        if user_id and result.get("tokens_used"):
            try:
                from ai_engine.middleware.rate_limit import record_token_usage

                record_token_usage(user_id, result["tokens_used"])
            except Exception:
                pass

        result["estimated_tokens"] = estimated_tokens
        result["estimated_cost_usd"] = estimated_cost_usd

        logger.info(
            "Agent task complete — success=%s tokens=%d cost=$%.6f time=%.2fs",
            result["success"],
            result.get("tokens_used", 0),
            result.get("cost_usd", 0.0),
            result.get("execution_time_s", 0.0),
        )
        return result

    def stream(
        self,
        task: str,
        tool_names: Optional[List[str]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Stream intermediate steps and the final answer (synchronous generator).

        Yields dicts of the form:
          {"step": {"thought": ..., "action": ..., "action_input": ...}}
          {"step": {"observation": ...}}
          {"final": {"answer": ..., "tokens_used": ..., "cost_usd": ..., "execution_time_s": ...}}
          {"error": str}
        """
        agent = self._make_agent(tool_names)
        logger.info(
            "Streaming agent task (tools=%s): %s", tool_names or "all", task[:120]
        )
        yield from agent.stream(task, extra_context=extra_context)

    async def astream(
        self,
        task: str,
        tool_names: Optional[List[str]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        INC-03: Async generator wrapper around the synchronous stream().

        Runs the blocking sync generator in a thread pool so it can be
        consumed from async contexts (Django async views, WebSocket consumers,
        FastAPI endpoints) without blocking the event loop.

        Usage::

            async for event in executor.astream("Summarise trending AI papers"):
                await websocket.send_json(event)
        """
        agent = self._make_agent(tool_names)
        logger.info(
            "Async-streaming agent task (tools=%s): %s", tool_names or "all", task[:120]
        )

        loop = asyncio.get_event_loop()
        sync_gen = agent.stream(task, extra_context=extra_context)

        while True:
            try:
                # Advance the sync generator off-thread to avoid blocking the event loop
                event = await loop.run_in_executor(None, next, sync_gen, _SENTINEL)
                if event is _SENTINEL:
                    break
                yield event
            except StopIteration:
                break
            except Exception as exc:
                logger.error("astream error: %s", exc)
                yield {"error": str(exc)}
                break

    def list_tools(self) -> List[Dict[str, str]]:
        """Return descriptions of all registered tools (for API /agents/tools endpoint)."""
        return self.registry.describe()

    def health(self) -> Dict[str, Any]:
        """Return health/status information about the executor."""
        return {
            "status": "ok",
            "tools_registered": len(self.registry),
            "tool_names": self.registry.list_tool_names(),
            "model": self.model_name,
            "max_iterations": self.max_iterations,
            "max_execution_time_s": self.max_execution_time,
        }


# Sentinel used by astream() to detect StopIteration safely from run_in_executor
_SENTINEL = object()


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------


def get_executor(
    scitely_api_key: Optional[str] = None,
    openrouter_api_key: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
) -> SynapseAgentExecutor:
    """Return a SynapseAgentExecutor.

    When per-user API keys are provided, a fresh (non-cached) executor is
    returned so that one user's keys are never shared with another.
    When no keys are provided, the module-level singleton is returned for
    efficiency (uses env-var keys shared across all requests).
    """
    global _executor_instance
    if scitely_api_key or openrouter_api_key or gemini_api_key:
        # Per-user executor — not cached
        return SynapseAgentExecutor(
            scitely_api_key=scitely_api_key,
            openrouter_api_key=openrouter_api_key,
            gemini_api_key=gemini_api_key,
        )
    if _executor_instance is None:
        _executor_instance = SynapseAgentExecutor()
    return _executor_instance
