"""
backend.apps.agents.tasks
~~~~~~~~~~~~~~~~~~~~~~~~~
Celery tasks for asynchronous agent task execution.

Phase 5.1 — Agent Framework (Week 13)

Flow:
    1. API creates AgentTask (status=pending) and queues execute_agent_task
    2. Celery worker picks it up → status=processing
    3. SynapseAgentExecutor.run() executes the ReAct loop
    4. Result saved → status=completed | failed
    5. Optional notification sent to user
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from celery import shared_task

logger = logging.getLogger(__name__)


def _extract_file_meta(answer: str, task_type: str) -> dict:
    """
    Parse file path / metadata from the agent's text answer for
    document and project tasks. Returns a dict with keys:
      file_path, file_name, file_size_bytes, download_url, file_list (project only)
    Falls back gracefully if nothing is found.
    """
    if task_type not in ("document", "project"):
        return {}

    meta: dict = {}

    # Look for "Path: /absolute/path/to/file.ext" or "File: relative/path"
    path_match = re.search(r"Path:\s*(.+?)(?:\n|$)", answer)
    file_match = re.search(r"File:\s*(.+?)(?:\n|$)", answer)
    raw_path = path_match or file_match
    if raw_path:
        p = Path(raw_path.group(1).strip())
        meta["file_path"] = str(p)
        meta["file_name"] = p.name

        # Build a media-relative download URL
        media_root = Path(
            os.environ.get("DJANGO_MEDIA_ROOT")
            or os.environ.get("MEDIA_ROOT")
            or "media"
        )
        try:
            rel = p.relative_to(media_root)
            meta["download_url"] = f"/media/{rel}"
        except ValueError:
            # Path not under media root — use as-is
            meta["download_url"] = f"/media/{p.name}"

        # File size
        try:
            if p.exists():
                meta["file_size_bytes"] = p.stat().st_size
        except Exception:
            pass

    # Size from text: "Size: 12,345 bytes"
    if "file_size_bytes" not in meta:
        size_match = re.search(r"Size:\s*([\d,]+)\s*bytes", answer)
        if size_match:
            try:
                meta["file_size_bytes"] = int(size_match.group(1).replace(",", ""))
            except ValueError:
                pass

    # For project tasks: extract file list from "Included files:\n  file1\n  file2"
    if task_type == "project":
        fl_match = re.search(r"Included files:\n((?:  .+\n?)+)", answer)
        if fl_match:
            lines = fl_match.group(1).strip().splitlines()
            meta["file_list"] = [ln.strip() for ln in lines if ln.strip()]

    return meta


def _build_user_context(user) -> dict:
    """
    Gather comprehensive user-specific app context so the AI agent can
    understand the user's full environment and provide informed answers.

    Returns a dict whose keys are context section names and values are
    concise string summaries. Only non-empty sections are included.
    """
    ctx: dict = {}

    try:
        # ── User profile ──────────────────────────────────────────
        name = getattr(user, "first_name", "") or user.email
        ctx["User"] = f"{name} (plan: {getattr(user, 'role', 'free')})"

        prefs = getattr(user, "preferences", {}) or {}
        interests = prefs.get("interests") or prefs.get("topics") or []
        if interests:
            ctx["Interests"] = ", ".join(interests[:10])

        # ── Onboarding preferences ────────────────────────────────
        try:
            from apps.users.models import OnboardingPreferences

            op = OnboardingPreferences.objects.filter(user=user, completed=True).first()
            if op:
                if op.interests:
                    ctx["Onboarding Interests"] = ", ".join(op.interests[:10])
                if getattr(op, "experience_level", None):
                    ctx["Experience Level"] = op.experience_level
        except Exception:
            pass

        # ── Active automations ────────────────────────────────────
        try:
            from apps.automation.models import Workflow

            active_wfs = list(
                Workflow.objects.filter(user=user, is_active=True).values_list(
                    "name", flat=True
                )[:10]
            )
            if active_wfs:
                ctx["Active Automations"] = ", ".join(active_wfs)
        except Exception:
            pass

        # ── Feed statistics ───────────────────────────────────────
        try:
            from apps.articles.models import Article
            from apps.papers.models import ResearchPaper
            from apps.repositories.models import Repository
            from apps.tweets.models import Tweet

            from django.db.models import Q

            tweet_count = Tweet.objects.filter(
                Q(user=user) | Q(user__isnull=True)
            ).count()
            article_count = Article.objects.filter(
                Q(user=user) | Q(user__isnull=True)
            ).count()
            repo_count = Repository.objects.filter(
                Q(user=user) | Q(user__isnull=True)
            ).count()
            paper_count = ResearchPaper.objects.filter(
                Q(user=user) | Q(user__isnull=True)
            ).count()
            ctx["Feed Data"] = (
                f"{tweet_count} tweets, {article_count} articles, "
                f"{repo_count} repositories, {paper_count} papers"
            )
        except Exception:
            pass

        # ── Configured integrations ───────────────────────────────
        integrations = []
        if prefs.get("scitely_api_key"):
            integrations.append("Scitely")
        if prefs.get("openrouter_api_key"):
            integrations.append("OpenRouter")
        if prefs.get("gemini_api_key"):
            integrations.append("Gemini")
        if prefs.get("x_api_key"):
            integrations.append("X/Twitter")
        if prefs.get("github_token"):
            integrations.append("GitHub")
        if integrations:
            ctx["Configured Integrations"] = ", ".join(integrations)
        else:
            ctx["Configured Integrations"] = (
                "None — suggest user to configure in Settings → AI Engine"
            )

        # ── Subscription / billing ────────────────────────────────
        try:
            from apps.billing.models import Subscription

            sub = Subscription.objects.filter(user=user, status="active").first()
            if sub:
                ctx["Subscription"] = (
                    f"{sub.plan} (active, renews {sub.current_period_end})"
                )
            else:
                ctx["Subscription"] = "Free tier"
        except Exception:
            ctx["Subscription"] = "Free tier"

        # ── Recent bookmarks ──────────────────────────────────────
        try:
            from apps.core.models import UserActivity

            bookmarks = list(
                UserActivity.objects.filter(user=user, interaction_type="bookmark")
                .order_by("-created_at")
                .values_list("object_id", flat=True)[:5]
            )
            if bookmarks:
                ctx["Recent Bookmarks"] = f"{len(bookmarks)} items bookmarked"
        except Exception:
            pass

    except Exception as exc:
        logger.debug("_build_user_context failed: %s", exc)

    return ctx


@shared_task(
    bind=True,
    name="apps.agents.tasks.execute_agent_task",
    queue="agents",
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=330,  # 5 min 30 s — slightly above agent max_execution_time
    time_limit=360,
)
def execute_agent_task(self, agent_task_id: str) -> dict:
    """
    Execute a SYNAPSE agent task asynchronously.

    Args:
        agent_task_id: UUID string of the AgentTask record to process.

    Returns:
        dict summarising success/failure (stored in Celery result backend).
    """
    from apps.agents.models import AgentTask

    # ── Fetch task record ─────────────────────────────────────────────
    try:
        task_obj = AgentTask.objects.get(id=agent_task_id)
    except AgentTask.DoesNotExist:
        logger.error("AgentTask %s not found", agent_task_id)
        return {"success": False, "error": "AgentTask not found"}

    # ── Mark as processing ────────────────────────────────────────────
    task_obj.status = AgentTask.TaskStatus.PROCESSING
    task_obj.celery_task_id = self.request.id or task_obj.celery_task_id or ""
    task_obj.save(update_fields=["status", "celery_task_id"])
    logger.info("AgentTask %s — starting (type=%s)", agent_task_id, task_obj.task_type)

    # ── Resolve tool subset from task_type ────────────────────────────
    tool_map: dict[str, list[str] | None] = {
        "research": ["search_knowledge_base", "fetch_articles", "fetch_arxiv_papers"],
        "trends": ["analyze_trends", "fetch_articles", "search_github"],
        "github": ["search_github"],
        "arxiv": ["fetch_arxiv_papers"],
        "tweets": ["search_knowledge_base", "fetch_articles", "analyze_trends"],
        "document": [
            "generate_pdf",
            "generate_ppt",
            "generate_word_doc",
            "generate_markdown",
            "search_knowledge_base",
            "fetch_articles",
        ],
        "project": ["create_project"],
        "general": None,  # all tools
    }
    tool_names = tool_map.get(task_obj.task_type, None)

    # ── Prepend task-type context to prompt ───────────────────────────
    task_context: dict[str, str] = {
        "research": (
            "Use search_knowledge_base and fetch_articles to find relevant information. "
            "Make at most 3 tool calls, then write a clear summary. "
        ),
        "trends": (
            "Use analyze_trends to get data, then summarize what you find. "
            "One tool call is enough. "
        ),
        "github": (
            "Use search_github to find repositories. Present the top results clearly. "
        ),
        "arxiv": (
            "Use fetch_arxiv_papers to find papers. If rate-limited, use your knowledge instead. "
        ),
        "tweets": (
            "You are analyzing X/Twitter (formerly Twitter) content for tech insights. "
            "Use search_knowledge_base to search the tweets database for relevant discussions. "
            "Use analyze_trends to identify what topics are trending. "
            "Use fetch_articles to supplement with recent tech news. "
            "Synthesize the information to identify: (1) key themes and topics, (2) top voices/authors, "
            "(3) emerging trends, (4) notable discussions and debates. "
            "Present findings in a clear, structured format with key insights highlighted. "
        ),
        "document": (
            "IMPORTANT: You must call the appropriate document generation tool (generate_pdf, "
            "generate_ppt, generate_word_doc, or generate_markdown) RIGHT NOW with content "
            "YOU write from your own knowledge. Do NOT ask the user for content. "
            "Create 3-5 informative sections with real, substantive content. "
            "Use user_id='anonymous'. After calling the tool, report the file path. "
        ),
        "project": (
            "Call create_project immediately with the project_type, name, and features "
            "extracted from the user request. Use user_id='anonymous'. "
        ),
        "general": "",
    }
    context_prefix = task_context.get(task_obj.task_type, "")
    augmented_prompt = (
        f"{context_prefix}{task_obj.prompt}" if context_prefix else task_obj.prompt
    )

    # ── Resolve per-user API keys (user prefs → env vars → Django settings) ──
    scitely_api_key = None
    openrouter_api_key = None
    gemini_api_key = None
    try:
        prefs = getattr(task_obj.user, "preferences", {}) or {}
        scitely_api_key = prefs.get("scitely_api_key") or None
        openrouter_api_key = prefs.get("openrouter_api_key") or None
        gemini_api_key = prefs.get("gemini_api_key") or None
    except Exception:
        pass

    # Fall back to environment / Django settings if user has no personal key
    if not scitely_api_key:
        scitely_api_key = os.environ.get("SCITELY_API_KEY") or None
    if not openrouter_api_key:
        from django.conf import settings as django_settings

        openrouter_api_key = (
            os.environ.get("OPENROUTER_API_KEY")
            or getattr(django_settings, "OPENROUTER_API_KEY", None)
            or None
        )
    if not gemini_api_key:
        from django.conf import settings as django_settings

        gemini_api_key = (
            os.environ.get("GEMINI_API_KEY")
            or getattr(django_settings, "GEMINI_API_KEY", None)
            or None
        )

    # ── Run the agent ─────────────────────────────────────────────────
    try:
        # Import here so Django/AI engine are fully initialised before use
        from ai_engine.agents import get_executor

        executor = get_executor(
            scitely_api_key=scitely_api_key,
            openrouter_api_key=openrouter_api_key,
            gemini_api_key=gemini_api_key,
        )

        # Build rich user context so the AI understands the whole app
        user_context = _build_user_context(task_obj.user)

        result = executor.run(
            task=augmented_prompt,
            tool_names=tool_names,
            extra_context=user_context,
        )

        # ── Save result ───────────────────────────────────────────────
        task_obj.status = (
            AgentTask.TaskStatus.COMPLETED
            if result["success"]
            else AgentTask.TaskStatus.FAILED
        )

        answer_text = result.get("answer", "")

        # ── Parse file metadata for document/project tasks ────────────
        file_meta = _extract_file_meta(answer_text, task_obj.task_type)

        task_obj.result = {
            "answer": answer_text,
            "intermediate_steps": result.get("intermediate_steps", []),
            "execution_time_s": result.get("execution_time_s", 0),
            **file_meta,
        }
        task_obj.tokens_used = result.get("tokens_used", 0)
        task_obj.cost_usd = result.get("cost_usd", 0.0)
        task_obj.error_message = result.get("error") or ""
        task_obj.completed_at = datetime.now(tz=timezone.utc)
        task_obj.save(
            update_fields=[
                "status",
                "result",
                "tokens_used",
                "cost_usd",
                "error_message",
                "completed_at",
            ]
        )

        logger.info(
            "AgentTask %s — %s (tokens=%d cost=$%.6f time=%.2fs)",
            agent_task_id,
            task_obj.status,
            task_obj.tokens_used,
            float(task_obj.cost_usd),
            result["execution_time_s"],
        )

        # ── Optional: create in-app notification ──────────────────────
        try:
            _notify_user(task_obj, result["success"])
        except Exception as notify_exc:
            logger.warning(
                "Notification failed for AgentTask %s: %s", agent_task_id, notify_exc
            )

        return {
            "success": result["success"],
            "agent_task_id": agent_task_id,
            "tokens_used": task_obj.tokens_used,
            "cost_usd": float(task_obj.cost_usd),
        }

    except ValueError as exc:
        # ValueError usually means missing API key configuration
        error_msg = str(exc)
        if "API_KEY" in error_msg or "api key" in error_msg.lower():
            error_msg = (
                "No AI provider configured. Please set one of: GROQ_API_KEY, "
                "OPENROUTER_API_KEY, GEMINI_API_KEY, or AI_GATEWAY_API_KEY in your "
                "Render environment variables."
            )
        logger.error("AgentTask %s — config error: %s", agent_task_id, error_msg)
        task_obj.status = AgentTask.TaskStatus.FAILED
        task_obj.error_message = error_msg
        task_obj.completed_at = datetime.now(tz=timezone.utc)
        task_obj.save(update_fields=["status", "error_message", "completed_at"])
        # Don't retry config errors
        return {"success": False, "error": error_msg, "agent_task_id": agent_task_id}

    except Exception as exc:
        logger.exception("AgentTask %s — unexpected error: %s", agent_task_id, exc)
        task_obj.status = AgentTask.TaskStatus.FAILED
        task_obj.error_message = str(exc)
        task_obj.completed_at = datetime.now(tz=timezone.utc)
        task_obj.save(update_fields=["status", "error_message", "completed_at"])

        # Retry if within retry budget
        raise self.retry(exc=exc)


def _notify_user(task_obj, success: bool) -> None:
    """Create an in-app notification for the task owner."""
    from apps.notifications.models import Notification

    status_str = "completed" if success else "failed"
    emoji = "✅" if success else "❌"

    Notification.objects.create(
        user=task_obj.user,
        title=f"{emoji} Agent task {status_str}",
        message=(
            f"Your agent task '{task_obj.task_type}' has {status_str}. "
            f"Tokens used: {task_obj.tokens_used} | "
            f"Cost: ${float(task_obj.cost_usd):.4f}"
        ),
        notif_type="info",
        metadata={
            "agent_task_id": str(task_obj.id),
            "task_type": task_obj.task_type,
            "tokens_used": task_obj.tokens_used,
            "cost_usd": float(task_obj.cost_usd),
        },
    )


@shared_task(
    name="apps.agents.tasks.cancel_agent_task",
    queue="agents",
)
def cancel_agent_task(agent_task_id: str, celery_task_id: str) -> dict:
    """
    Attempt to cancel a running agent task by revoking its Celery task.

    Args:
        agent_task_id:  UUID of the AgentTask record.
        celery_task_id: Celery task ID to revoke.
    """
    from apps.agents.models import AgentTask

    from celery.app.control import Control

    from config.celery import app as celery_app

    try:
        task_obj = AgentTask.objects.get(id=agent_task_id)
    except AgentTask.DoesNotExist:
        return {"success": False, "error": "AgentTask not found"}

    if task_obj.status in (AgentTask.TaskStatus.COMPLETED, AgentTask.TaskStatus.FAILED):
        return {"success": False, "error": f"Task already {task_obj.status}"}

    # Revoke the Celery task
    control = Control(app=celery_app)
    control.revoke(celery_task_id, terminate=True, signal="SIGTERM")

    task_obj.status = AgentTask.TaskStatus.FAILED
    task_obj.error_message = "Cancelled by user"
    task_obj.completed_at = datetime.now(tz=timezone.utc)
    task_obj.save(update_fields=["status", "error_message", "completed_at"])

    logger.info(
        "AgentTask %s cancelled (celery_task_id=%s)", agent_task_id, celery_task_id
    )
    return {"success": True, "agent_task_id": agent_task_id}
