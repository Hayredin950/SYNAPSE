"""
Celery tasks for the Automation app.

Action types supported:
  - collect_news       : trigger scraping tasks per source
  - summarize_content  : trigger NLP + summarization for pending articles
  - generate_pdf       : AI-powered PDF via doc_tools, content from recent articles
  - send_email         : in-app notification + SendGrid email to workflow owner
  - upload_to_drive    : upload file to the user's Google Drive
  - ai_digest          : use the AI agent to research a topic and return a digest
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Action handlers ────────────────────────────────────────────────────────────


def _action_scrape_videos(params: dict, workflow=None) -> dict:
    """
    Scrape YouTube videos based on user-configured queries and settings.
    User can configure max_results in the workflow params (default: 5).
    """
    try:
        from apps.core.tasks import scrape_youtube

        # Parse queries: may be a newline-separated string or a list
        raw_queries = params.get("queries", "")
        if isinstance(raw_queries, str):
            queries = [q.strip() for q in raw_queries.strip().splitlines() if q.strip()]
        elif isinstance(raw_queries, list):
            queries = [q.strip() for q in raw_queries if q.strip()]
        else:
            queries = []

        # User-configurable: default is 5, can be changed in Automation page
        max_results = int(params.get("max_results", params.get("limit", 5)))
        days_back = int(params.get("days_back", 30))

        user_id = str(workflow.user_id) if workflow else None
        # Note: scrape_youtube is routed to "slow_scraping" queue via task_routes in settings
        task = scrape_youtube.apply_async(
            kwargs={
                "days_back": days_back,
                "max_results": max_results,
                "queries": queries if queries else None,
                "user_id": user_id,
            },
            queue="slow_scraping",
        )

        return {
            "action": "scrape_videos",
            "status": "queued",
            "task_id": task.id,
            "queries": queries or "default",
            "max_results": max_results,
            "days_back": days_back,
        }
    except Exception as exc:
        logger.exception("scrape_videos action failed: %s", exc)
        return {"action": "scrape_videos", "status": "error", "error": str(exc)}


def _action_scrape_tweets(params: dict, workflow=None) -> dict:
    """
    Scrape X/Twitter tweets via Nitter.
    User can configure max_results in workflow params (default: 5).
    """
    try:
        from apps.core.tasks import scrape_twitter

        raw_queries = params.get("queries", "")
        if isinstance(raw_queries, str):
            queries = [q.strip() for q in raw_queries.strip().splitlines() if q.strip()]
        elif isinstance(raw_queries, list):
            queries = [q.strip() for q in raw_queries if q.strip()]
        else:
            queries = []

        # User-configurable: default is 5, can be changed in Automation page
        max_results = int(params.get("max_results", params.get("limit", 5)))
        user_id = str(workflow.user_id) if workflow else None
        task_ids = []

        if queries:
            # Dispatch one Nitter task per query for broader coverage
            per_query = max(1, max_results // len(queries))
            for q in queries:
                t = scrape_twitter.apply_async(
                    kwargs={
                        "query": q,
                        "max_results": per_query,
                        "user_id": user_id,
                        "use_nitter": True,
                    },
                    queue="scraping",
                )
                task_ids.append(t.id)
        else:
            # No queries — scrape default tech accounts via Nitter
            t = scrape_twitter.apply_async(
                kwargs={
                    "max_results": max_results,
                    "user_id": user_id,
                    "use_nitter": True,
                },
                queue="scraping",
            )
            task_ids.append(t.id)

        return {
            "action": "scrape_tweets",
            "status": "queued",
            "task_ids": task_ids,
            "tasks_count": len(task_ids),
            "queries": queries or "default tech accounts",
            "max_results": max_results,
        }
    except Exception as exc:
        logger.exception("scrape_tweets action failed: %s", exc)
        return {"action": "scrape_tweets", "status": "error", "error": str(exc)}


def _action_collect_news(params: dict, workflow=None) -> dict:
    """Trigger scraping tasks for specified sources. User-configurable item counts."""
    from apps.core.tasks import (
        scrape_arxiv,
        scrape_github,
        scrape_hackernews,
        scrape_twitter,
        scrape_youtube,
    )

    sources = params.get(
        "sources", ["hackernews", "github", "arxiv", "youtube", "twitter"]
    )
    task_ids = {}
    user_id = str(workflow.user_id) if workflow else None

    # User can configure these in Automation page - defaults are sensible starting points
    DEFAULT_ITEMS_PER_SOURCE = 5

    if "hackernews" in sources:
        # Use 'limit' from workflow params, fallback to items_per_source, then default
        hn_limit = int(
            params.get(
                "limit", params.get("items_per_source", DEFAULT_ITEMS_PER_SOURCE)
            )
        )
        t = scrape_hackernews.apply_async(
            kwargs={
                "story_type": params.get("story_type", "top"),
                "limit": hn_limit,
                "user_id": user_id,
            },
            queue="scraping",
        )
        task_ids["hackernews"] = t.id

    if "github" in sources:
        gh_limit = int(
            params.get(
                "limit", params.get("items_per_source", DEFAULT_ITEMS_PER_SOURCE)
            )
        )
        t = scrape_github.apply_async(
            kwargs={
                "days_back": int(params.get("days_back", 7)),
                "language": None,
                "limit": gh_limit,
                "user_id": user_id,
            },
            queue="scraping",
        )
        task_ids["github"] = t.id

    if "arxiv" in sources:
        arxiv_limit = int(
            params.get(
                "max_papers", params.get("items_per_source", DEFAULT_ITEMS_PER_SOURCE)
            )
        )
        # arXiv uses slow_scraping queue due to API rate limits
        t = scrape_arxiv.apply_async(
            kwargs={
                "categories": params.get("categories"),  # Allow user-configured categories
                "days_back": int(params.get("days_back", 7)),
                "max_papers": arxiv_limit,
                "user_id": user_id,
            },
            queue="slow_scraping",
        )
        task_ids["arxiv"] = t.id

    if "youtube" in sources:
        # Parse youtube_queries from params (newline-separated string or list)
        raw_yt_queries = params.get("queries", params.get("youtube_queries", "")) or ""
        if isinstance(raw_yt_queries, str):
            yt_queries = [q.strip() for q in raw_yt_queries.splitlines() if q.strip()]
        elif isinstance(raw_yt_queries, list):
            yt_queries = [q.strip() for q in raw_yt_queries if q.strip()]
        else:
            yt_queries = []

        yt_limit = int(
            params.get(
                "max_results", params.get("items_per_source", DEFAULT_ITEMS_PER_SOURCE)
            )
        )
        # YouTube uses slow_scraping queue due to yt-dlp rate limits
        t = scrape_youtube.apply_async(
            kwargs={
                "days_back": int(params.get("days_back", 30)),
                "max_results": yt_limit,
                "queries": yt_queries if yt_queries else None,
                "user_id": user_id,
            },
            queue="slow_scraping",
        )
        task_ids["youtube"] = t.id

    if "twitter" in sources:
        # Parse twitter_queries from params (newline-separated string or list)
        raw_tw_queries = params.get("twitter_queries", "") or ""
        if isinstance(raw_tw_queries, str):
            tw_queries = [q.strip() for q in raw_tw_queries.splitlines() if q.strip()]
        elif isinstance(raw_tw_queries, list):
            tw_queries = [q.strip() for q in raw_tw_queries if q.strip()]
        else:
            tw_queries = []

        tw_limit = int(params.get("items_per_source", DEFAULT_ITEMS_PER_SOURCE))
        t = scrape_twitter.apply_async(
            kwargs={
                "queries": ",".join(tw_queries) if tw_queries else None,
                "max_results": tw_limit,
                "user_id": user_id,
                "use_nitter": True,
            },
            queue="scraping",
        )
        task_ids["twitter"] = t.id

    return {"action": "collect_news", "status": "queued", "task_ids": task_ids}


def _action_summarize_content(params: dict) -> dict:
    """Trigger NLP + summarization for pending articles."""
    from apps.articles.tasks import (
        process_pending_articles_nlp,
        summarize_pending_articles,
    )

    batch_size = params.get("batch_size", 20)
    nlp_task = process_pending_articles_nlp.apply_async(args=[batch_size], queue="nlp")
    sum_task = summarize_pending_articles.apply_async(args=[batch_size], queue="nlp")

    return {
        "action": "summarize_content",
        "status": "queued",
        "task_ids": {
            "nlp": nlp_task.id,
            "summarize": sum_task.id,
        },
    }


def _build_pdf_sections(params: dict, workflow) -> list:
    """
    Build section content for the PDF.
    If 'sections' are provided explicitly, use them directly.
    Otherwise fetch recent articles from the DB and turn each into a section.
    """
    explicit = params.get("sections")
    if explicit:
        return explicit

    # Auto-build from recent articles
    try:
        from apps.articles.models import Article

        topic_filter = params.get("topic", "")
        qs = Article.objects.all().order_by("-published_at")
        if topic_filter:
            qs = qs.filter(title__icontains=topic_filter)
        limit = int(params.get("article_limit", 5))
        articles = list(qs[:limit])

        sections = []
        for art in articles:
            content = art.summary or art.content or art.description or ""
            if not content:
                continue
            sections.append(
                {
                    "heading": art.title[:120],
                    "content": content[:2000],
                }
            )

        if not sections:
            sections = [
                {
                    "heading": "Summary",
                    "content": "No recent articles found for this report.",
                }
            ]
        return sections
    except Exception as e:
        logger.warning("_build_pdf_sections: could not fetch articles: %s", e)
        return [
            {"heading": "Summary", "content": "Auto-generated report from SYNAPSE."}
        ]


def _action_generate_pdf(params: dict, workflow=None) -> dict:
    """
    Generate a PDF using the AI doc_tools engine.
    Pulls recent articles from the DB if no sections provided explicitly.
    Saves a GeneratedDocument record so the file is accessible in the Documents UI.
    """
    try:
        from ai_engine.agents.doc_tools import _generate_pdf

        title = params.get(
            "title", f"SYNAPSE Report — {timezone.now().strftime('%Y-%m-%d')}"
        )
        subtitle = params.get("subtitle", "Auto-generated by SYNAPSE Automation")
        author = params.get("author", "SYNAPSE Automation")
        user_id = (
            str(workflow.user_id) if workflow else params.get("user_id", "automation")
        )

        sections = _build_pdf_sections(params, workflow)

        result_str = _generate_pdf(
            title=title,
            sections=sections,
            subtitle=subtitle,
            author=author,
            user_id=user_id,
        )

        # Parse file path from result string and create a GeneratedDocument record
        file_path = ""
        for line in result_str.splitlines():
            if line.startswith("Path:"):
                file_path = line.split("Path:", 1)[1].strip()
                break

        if file_path and workflow:
            try:
                from apps.documents.models import GeneratedDocument

                GeneratedDocument.objects.create(
                    user=workflow.user,
                    title=title,
                    doc_type="pdf",
                    file_path=file_path,
                    metadata={
                        "workflow_id": str(workflow.id),
                        "sections": len(sections),
                        "subtitle": subtitle,
                    },
                )
            except Exception as doc_exc:
                logger.warning(
                    "generate_pdf: could not save GeneratedDocument: %s", doc_exc
                )

        return {
            "action": "generate_pdf",
            "status": "completed",
            "title": title,
            "sections": len(sections),
            "file_path": file_path,
            "result": result_str,
        }
    except Exception as exc:
        logger.warning("generate_pdf action failed: %s", exc)
        return {
            "action": "generate_pdf",
            "status": "failed",
            "error": str(exc),
        }


def _action_send_email(workflow, params: dict) -> dict:
    """Create an in-app notification and queue a SendGrid email for the workflow owner."""
    try:
        from apps.notifications.models import Notification
        from apps.notifications.tasks import send_notification_email_task

        notif = Notification.objects.create(
            user=workflow.user,
            title=params.get("subject", f"Workflow '{workflow.name}' completed"),
            message=params.get(
                "body", f"Your workflow '{workflow.name}' has completed successfully."
            ),
            notif_type="workflow_complete",
            metadata={"workflow_id": str(workflow.id)},
        )
        send_notification_email_task.delay(str(notif.id))
        # Push real-time WebSocket notification to the workflow owner
        try:
            from apps.notifications.tasks import push_notification_to_ws

            push_notification_to_ws(notif)
        except Exception as ws_exc:
            logger.warning("WS push failed (non-critical): %s", ws_exc)

        return {
            "action": "send_email",
            "status": "notification_created",
            "notification_id": str(notif.id),
        }
    except Exception as exc:
        logger.warning("send_email action failed: %s", exc)
        return {"action": "send_email", "status": "failed", "error": str(exc)}


def _action_upload_to_drive(params: dict, workflow=None) -> dict:
    """
    Upload a file to the user's Google Drive.
    Looks up the user's stored GoogleDriveToken for credentials.
    file_path param can be an absolute path or a path produced by generate_pdf.
    """
    try:
        from apps.integrations.google_drive import upload_to_drive
        from apps.integrations.models import GoogleDriveToken

        file_path = params.get("file_path", "")
        folder_name = params.get("folder_name", "SYNAPSE")
        file_name = params.get("file_name") or None

        if not file_path:
            return {
                "action": "upload_to_drive",
                "status": "skipped",
                "reason": "No file_path provided.",
            }

        # Resolve user credentials
        credentials_dict = None
        if workflow:
            try:
                token_obj = GoogleDriveToken.objects.get(user=workflow.user)
                credentials_dict = token_obj.get_credentials()
            except GoogleDriveToken.DoesNotExist:
                return {
                    "action": "upload_to_drive",
                    "status": "skipped",
                    "reason": (
                        "Google Drive not connected. "
                        "Visit Settings → Integrations to connect your Drive."
                    ),
                }

        if not credentials_dict:
            return {
                "action": "upload_to_drive",
                "status": "skipped",
                "reason": "No Google Drive credentials available.",
            }

        result = upload_to_drive(
            file_path=file_path,
            folder_name=folder_name,
            credentials_dict=credentials_dict,
            file_name=file_name,
        )
        return {
            "action": "upload_to_drive",
            "status": "completed",
            "file_id": result.get("id"),
            "file_name": result.get("name"),
            "web_view_link": result.get("webViewLink"),
        }
    except FileNotFoundError as fnf:
        logger.warning("upload_to_drive: file not found: %s", fnf)
        return {"action": "upload_to_drive", "status": "failed", "error": str(fnf)}
    except ImportError:
        logger.info("upload_to_drive: Google Drive integration not available.")
        return {
            "action": "upload_to_drive",
            "status": "skipped",
            "reason": "Google Drive integration not configured.",
        }
    except Exception as exc:
        logger.warning("upload_to_drive action failed: %s", exc)
        return {"action": "upload_to_drive", "status": "failed", "error": str(exc)}


def _action_ai_digest(params: dict, workflow=None) -> dict:
    """
    Use the SYNAPSE AI agent to research a topic and return a digest.
    Uses the workflow owner's API keys if configured, falls back to env vars.
    """
    try:
        from ai_engine.agents.executor import get_executor

        # Resolve per-user API keys from the workflow owner's preferences
        openrouter_api_key = None
        gemini_api_key = None
        if workflow:
            try:
                prefs = getattr(workflow.user, "preferences", {}) or {}
                openrouter_api_key = prefs.get("openrouter_api_key") or None
                gemini_api_key = prefs.get("gemini_api_key") or None
            except Exception:
                pass

        topic = params.get("topic", "latest AI research and tech news")
        tool_names = params.get(
            "tool_names", ["search_knowledge_base", "fetch_articles", "analyze_trends"]
        )
        executor = get_executor(
            openrouter_api_key=openrouter_api_key,
            gemini_api_key=gemini_api_key,
        )
        result = executor.run(
            task=f"Research and summarize: {topic}",
            tool_names=tool_names,
            user_id=str(workflow.user_id) if workflow else None,
            role=getattr(workflow.user, "role", "user") if workflow else "user",
        )

        return {
            "action": "ai_digest",
            "status": "completed",
            "topic": topic,
            "answer": result.get("answer", ""),
            "tokens_used": result.get("tokens_used", 0),
        }
    except Exception as exc:
        logger.warning("ai_digest action failed: %s", exc)
        return {"action": "ai_digest", "status": "failed", "error": str(exc)}


# ── Action dispatcher ──────────────────────────────────────────────────────────


def _dispatch_action(workflow, action: dict) -> dict:
    """Dispatch a single workflow action to its handler."""
    action_type = action.get("type", "")
    params = action.get("params", {})

    if action_type == "send_email":
        return _action_send_email(workflow, params)
    if action_type == "scrape_videos":
        return _action_scrape_videos(params, workflow=workflow)
    if action_type == "scrape_tweets":
        return _action_scrape_tweets(params, workflow=workflow)
    if action_type == "collect_news":
        return _action_collect_news(params, workflow=workflow)
    if action_type == "scrape_hackernews":
        return _action_collect_news({**params, "sources": ["hackernews"]}, workflow=workflow)
    if action_type == "scrape_github":
        return _action_collect_news({**params, "sources": ["github"]}, workflow=workflow)
    if action_type == "scrape_arxiv":
        return _action_collect_news({**params, "sources": ["arxiv"]}, workflow=workflow)
    if action_type == "summarize_content":
        return _action_summarize_content(params)
    if action_type == "generate_pdf":
        return _action_generate_pdf(params, workflow=workflow)
    if action_type == "upload_to_drive":
        return _action_upload_to_drive(params, workflow=workflow)
    if action_type == "ai_digest":
        return _action_ai_digest(params, workflow=workflow)

    logger.warning("Unknown action type '%s' in workflow %s", action_type, workflow.id)
    return {"action": action_type, "status": "skipped", "reason": "Unknown action type"}


# ── Main execution task ────────────────────────────────────────────────────────


@shared_task(
    bind=True,
    max_retries=2,
    queue="default",
    name="apps.automation.tasks.execute_workflow",
    soft_time_limit=300,  # 5 minutes soft limit
    time_limit=400,  # ~6.5 minutes hard limit
)
def execute_workflow(
    self, workflow_id: str, trigger_event: dict | None = None, run_id: str | None = None
) -> dict:
    """
    Execute all actions defined in an AutomationWorkflow sequentially.

    Args:
        workflow_id:    UUID string of the AutomationWorkflow to execute.
        trigger_event:  Optional dict describing the event that fired this run
                        (e.g. {'event_type': 'new_article', 'article_id': '...'}).
        run_id:         Optional UUID string of a pre-created WorkflowRun record.
                        When provided (manual trigger via the API), the task reuses
                        that record instead of creating a new one, so the frontend
                        can start polling immediately without a race condition.
    Returns:
        dict with execution summary.
    """
    from .models import AutomationWorkflow, WorkflowRun

    task_id = self.request.id
    logger.info("[%s] Executing workflow %s (run_id=%s)", task_id, workflow_id, run_id)

    try:
        workflow = AutomationWorkflow.objects.get(id=workflow_id)
    except AutomationWorkflow.DoesNotExist:
        logger.error("[%s] Workflow %s not found.", task_id, workflow_id)
        return {"status": "failed", "error": "Workflow not found"}

    if not workflow.is_active:
        logger.info("[%s] Workflow %s is inactive — skipping.", task_id, workflow_id)
        return {"status": "skipped", "reason": "Workflow is not active"}

    # Re-use a pre-created WorkflowRun (manual trigger) or create a fresh one
    # (schedule / event triggers that still call without run_id).
    if run_id:
        try:
            run = WorkflowRun.objects.get(id=run_id)
            run.status = WorkflowRun.RunStatus.RUNNING
            run.celery_task_id = task_id or ""
            run.trigger_event = trigger_event or run.trigger_event or {}
            run.save(update_fields=["status", "celery_task_id", "trigger_event"])
        except WorkflowRun.DoesNotExist:
            logger.warning(
                "[%s] Pre-created run %s not found; creating new.", task_id, run_id
            )
            run = WorkflowRun.objects.create(
                workflow=workflow,
                status=WorkflowRun.RunStatus.RUNNING,
                celery_task_id=task_id or "",
                trigger_event=trigger_event or {},
            )
    else:
        run = WorkflowRun.objects.create(
            workflow=workflow,
            status=WorkflowRun.RunStatus.RUNNING,
            celery_task_id=task_id or "",
            trigger_event=trigger_event or {},
        )

    workflow.status = AutomationWorkflow.Status.ACTIVE
    workflow.save(update_fields=["status", "updated_at"])

    action_results = []
    had_error = False

    try:
        for action in workflow.actions:
            action_type = action.get("type", "unknown")
            logger.info(
                "[%s] Running action '%s' for workflow %s",
                task_id,
                action_type,
                workflow_id,
            )
            try:
                result = _dispatch_action(workflow, action)
                action_results.append(result)
                # An action that returns status='failed' is a soft failure:
                # keep running subsequent actions but mark the overall run failed.
                if result.get("status") in ("failed", "error"):
                    had_error = True
            except Exception as action_exc:
                logger.error(
                    "[%s] Action '%s' raised: %s",
                    task_id,
                    action_type,
                    action_exc,
                    exc_info=True,
                )
                action_results.append(
                    {
                        "action": action_type,
                        "status": "error",
                        "error": str(action_exc),
                    }
                )
                had_error = True

        run.status = (
            WorkflowRun.RunStatus.FAILED if had_error else WorkflowRun.RunStatus.SUCCESS
        )
        run.completed_at = timezone.now()
        run.result = {"actions": action_results}
        if had_error:
            errors = [
                r.get("error", "")
                for r in action_results
                if r.get("status") in ("error", "failed") and r.get("error")
            ]
            run.error_message = "; ".join(errors)
        run.save(update_fields=["status", "completed_at", "result", "error_message"])

        # After a successful scraping run, regenerate the user's daily briefing
        # so the home page reflects the newly scraped data immediately.
        # We use a generous countdown because scraping tasks run as subprocesses
        # and can take 30-180 seconds each. The countdown starts from when the
        # workflow finishes queuing (not from when scrapers finish).
        SCRAPING_ACTIONS = {"collect_news", "scrape_videos", "scrape_tweets"}
        if not had_error:
            action_types = {a.get("type") for a in workflow.actions}
            if action_types & SCRAPING_ACTIONS:
                try:
                    from apps.core.tasks import generate_user_briefing

                    countdown_seconds = 180  # 3 min — enough for all scrapers to finish
                    generate_user_briefing.apply_async(
                        kwargs={"user_id": str(workflow.user_id)},
                        countdown=countdown_seconds,
                    )
                    logger.info(
                        "[%s] Queued briefing regeneration for user %s in %ds after %s",
                        task_id,
                        workflow.user_id,
                        countdown_seconds,
                        action_types & SCRAPING_ACTIONS,
                    )
                except Exception as brief_exc:
                    logger.warning(
                        "[%s] Could not queue briefing regeneration: %s",
                        task_id,
                        brief_exc,
                    )

        now = timezone.now()
        workflow.last_run_at = now
        workflow.run_count = workflow.run_count + 1
        workflow.status = (
            AutomationWorkflow.Status.FAILED
            if had_error
            else AutomationWorkflow.Status.ACTIVE
        )
        workflow.save(
            update_fields=["last_run_at", "run_count", "status", "updated_at"]
        )

        logger.info(
            "[%s] Workflow %s completed (%s)",
            task_id,
            workflow_id,
            "with errors" if had_error else "successfully",
        )
        return {
            "workflow_id": workflow_id,
            "run_id": str(run.id),
            "status": run.status,
            "actions": action_results,
        }

    except Exception as exc:
        logger.error("[%s] Workflow %s execution error: %s", task_id, workflow_id, exc)
        run.status = WorkflowRun.RunStatus.FAILED
        run.completed_at = timezone.now()
        run.error_message = str(exc)
        run.save(update_fields=["status", "completed_at", "error_message"])

        workflow.status = AutomationWorkflow.Status.FAILED
        workflow.save(update_fields=["status", "updated_at"])

        # Do NOT retry — the run is already marked FAILED in the DB.
        # Retrying would flip the run back to RUNNING and confuse the frontend.
        return {"status": "failed", "error": str(exc), "run_id": str(run.id)}


# ── Event trigger dispatcher ───────────────────────────────────────────────────


@shared_task(name="apps.automation.tasks.dispatch_event_trigger", queue="default")
def dispatch_event_trigger(event_type: str, event_payload: dict) -> dict:
    """
    Called when a system event occurs (new article, trending spike, etc.).
    Finds all active event-triggered workflows that match and fires them.

    Args:
        event_type:    One of 'new_article', 'trending_spike', 'new_paper', 'new_repo'
        event_payload: Dict with event-specific data (article_id, topic, score, etc.)

    Returns:
        Dict summarising how many workflows were fired.
    """
    from .models import AutomationWorkflow

    matching = AutomationWorkflow.objects.filter(
        trigger_type=AutomationWorkflow.TriggerType.EVENT,
        is_active=True,
    )

    fired = 0
    for workflow in matching:
        cfg = workflow.event_config or {}
        wf_event_type = cfg.get("event_type", "")

        # Must match the event type
        if wf_event_type != event_type:
            continue

        # Optional topic/keyword filter
        topic_filter = cfg.get("filter", {}).get("topic", "").lower()
        if topic_filter:
            payload_text = " ".join(str(v) for v in event_payload.values()).lower()
            if topic_filter not in payload_text:
                continue

        # Cooldown check: don't re-fire within cooldown_minutes
        cooldown = int(cfg.get("cooldown_minutes", 60))
        if workflow.last_run_at:
            elapsed = (timezone.now() - workflow.last_run_at).total_seconds() / 60
            if elapsed < cooldown:
                logger.info(
                    "Workflow %s skipped (cooldown: %d min remaining)",
                    workflow.id,
                    int(cooldown - elapsed),
                )
                continue

        execute_workflow.delay(str(workflow.id), trigger_event=event_payload)
        fired += 1
        logger.info(
            "Event '%s' fired workflow %s (%s)",
            event_type,
            workflow.id,
            workflow.name,
        )

    return {"event_type": event_type, "workflows_fired": fired}


# ── Cleanup task ───────────────────────────────────────────────────────────────


@shared_task(name="apps.automation.tasks.cleanup_stale_runs", queue="default")
def cleanup_stale_runs() -> dict:
    """Mark WorkflowRun records stuck in 'running' > 1 hour as failed."""
    from .models import WorkflowRun

    cutoff = timezone.now() - timedelta(minutes=5)
    stale = WorkflowRun.objects.filter(
        status__in=[WorkflowRun.RunStatus.RUNNING, WorkflowRun.RunStatus.PENDING],
        started_at__lt=cutoff,
    )
    count = stale.count()
    stale.update(
        status=WorkflowRun.RunStatus.FAILED,
        completed_at=timezone.now(),
        error_message="Run timed out — worker likely crashed.",
    )
    logger.info("cleanup_stale_runs: marked %d stale runs as failed.", count)
    return {"cleaned_up": count}
