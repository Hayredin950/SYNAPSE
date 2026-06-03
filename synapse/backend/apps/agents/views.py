"""
backend.apps.agents.views
~~~~~~~~~~~~~~~~~~~~~~~~~
REST API views for the SYNAPSE Agentic AI framework.

Endpoints (Phase 5.1 + 5.4):
  POST   /api/v1/agents/tasks/              — create + queue an agent task
  GET    /api/v1/agents/tasks/              — list user's tasks (paginated)
  GET    /api/v1/agents/tasks/{id}/         — retrieve task detail + result
  POST   /api/v1/agents/tasks/{id}/cancel/  — cancel a running task
  GET    /api/v1/agents/tasks/{id}/stream/  — SSE stream for real-time progress
  GET    /api/v1/agents/tools/              — list all registered tools
  GET    /api/v1/agents/health/             — executor health check

Phase 5.1 — Agent Framework (Week 13)
Phase 5.4 — Agent UI / SSE Streaming (Week 16)
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from apps.core.throttles import AgentRateThrottle

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

# Ensure the project root (containing ai_engine/) is on the path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from apps.core.pagination import StandardPagination

from .models import AgentTask, PromptTemplate, PromptUpvote
from .serializers import (
    AgentTaskCreateSerializer,
    AgentTaskListSerializer,
    AgentTaskSerializer,
    AgentToolDescriptionSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task list + create
# ---------------------------------------------------------------------------


class AgentTaskListCreateView(APIView):
    """
    GET  — Return paginated list of the authenticated user's agent tasks.
    POST — Create and immediately queue a new agent task.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = []

    def get(self, request: Request) -> Response:
        qs = AgentTask.objects.filter(user=request.user).order_by("-created_at")

        # Optional status filter: ?status=completed
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        # Optional task_type filter: ?task_type=research
        task_type_filter = request.query_params.get("task_type")
        if task_type_filter:
            qs = qs.filter(task_type=task_type_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AgentTaskListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request) -> Response:
        serializer = AgentTaskCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Sanitize prompt to prevent injection
        raw_prompt = serializer.validated_data["prompt"]
        try:
            from apps.core.security import sanitise_text  # noqa: PLC0415

            safe_prompt = sanitise_text(raw_prompt)
        except Exception:
            safe_prompt = raw_prompt[:4000]  # hard cap if sanitiser unavailable

        # Create the AgentTask record
        task_obj = AgentTask.objects.create(
            user=request.user,
            task_type=serializer.validated_data["task_type"],
            prompt=safe_prompt,
            status=AgentTask.TaskStatus.PENDING,
        )

        # Queue the Celery task.
        # When CELERY_ALWAYS_EAGER=True (Replit, no Redis) tasks run synchronously,
        # which would block this HTTP response for up to 5 minutes. We detect this
        # and run the task in a daemon thread so the response returns immediately
        # while the agent executes in the background.
        try:
            from .tasks import execute_agent_task
            from django.conf import settings as _dj_settings

            _eager = getattr(_dj_settings, "CELERY_TASK_ALWAYS_EAGER", False) or \
                     getattr(_dj_settings, "CELERY_ALWAYS_EAGER", False)

            if _eager:
                import threading
                import uuid as _uuid

                fake_task_id = str(_uuid.uuid4())
                task_obj.celery_task_id = fake_task_id
                task_obj.save(update_fields=["celery_task_id"])

                def _run():
                    try:
                        execute_agent_task(str(task_obj.id))
                    except Exception as _exc:
                        logger.error("Background AgentTask %s failed: %s", task_obj.id, _exc)

                t = threading.Thread(target=_run, daemon=True, name=f"agent-{task_obj.id}")
                t.start()
                logger.info("Dispatched AgentTask %s in background thread %s", task_obj.id, fake_task_id)
            else:
                celery_result = execute_agent_task.delay(str(task_obj.id))
                task_obj.celery_task_id = celery_result.id
                task_obj.save(update_fields=["celery_task_id"])
                logger.info("Queued AgentTask %s → Celery %s", task_obj.id, celery_result.id)
        except Exception as exc:
            logger.error("Failed to queue AgentTask %s: %s", task_obj.id, exc)
            task_obj.status = AgentTask.TaskStatus.FAILED
            task_obj.error_message = f"Failed to queue task: {exc}"
            task_obj.save(update_fields=["status", "error_message"])
            return Response(
                {"error": "Failed to queue agent task. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            AgentTaskSerializer(task_obj).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Task detail
# ---------------------------------------------------------------------------


class AgentTaskDetailView(APIView):
    """GET /api/v1/agents/tasks/{id}/ — retrieve full task detail including result."""

    permission_classes = [IsAuthenticated]

    def _get_task(self, task_id: str, user) -> AgentTask | None:
        try:
            return AgentTask.objects.get(id=task_id, user=user)
        except AgentTask.DoesNotExist:
            return None

    def get(self, request: Request, task_id: str) -> Response:
        task_obj = self._get_task(task_id, request.user)
        if not task_obj:
            return Response(
                {"error": "Agent task not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(AgentTaskSerializer(task_obj).data)


# ---------------------------------------------------------------------------
# Task cancel
# ---------------------------------------------------------------------------


class AgentTaskCancelView(APIView):
    """POST /api/v1/agents/tasks/{id}/cancel/ — cancel a pending/processing task."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: str) -> Response:
        try:
            task_obj = AgentTask.objects.get(id=task_id, user=request.user)
        except AgentTask.DoesNotExist:
            return Response(
                {"error": "Agent task not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if task_obj.status in (
            AgentTask.TaskStatus.COMPLETED,
            AgentTask.TaskStatus.FAILED,
        ):
            return Response(
                {"error": f"Cannot cancel a task with status '{task_obj.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from .tasks import cancel_agent_task

            cancel_agent_task.delay(str(task_obj.id), task_obj.celery_task_id)
            return Response(
                {"message": "Cancellation requested.", "task_id": str(task_obj.id)}
            )
        except Exception as exc:
            logger.error("Cancel failed for AgentTask %s: %s", task_obj.id, exc)
            return Response(
                {"error": f"Cancellation failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ---------------------------------------------------------------------------
# Tool list
# ---------------------------------------------------------------------------


class AgentToolListView(APIView):
    """GET /api/v1/agents/tools/ — list all registered agent tools."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        try:
            from ai_engine.agents import get_executor

            executor = get_executor()
            tools = executor.list_tools()
        except Exception as exc:
            logger.error("Failed to load agent tools: %s", exc)
            tools = []

        serializer = AgentToolDescriptionSerializer(tools, many=True)
        return Response({"tools": serializer.data, "count": len(tools)})


# ---------------------------------------------------------------------------
# SSE streaming — real-time task progress (Phase 5.4)
# ---------------------------------------------------------------------------


def agent_task_stream(request, task_id: str) -> StreamingHttpResponse:
    """
    GET /api/v1/agents/tasks/{id}/stream/

    Server-Sent Events endpoint — plain Django view (bypasses DRF content
    negotiation so it can return text/event-stream without a 406 error).

    Authentication: Bearer JWT token in Authorization header, or
                    ?token=<jwt> query-param for EventSource clients
                    (EventSource API cannot set custom headers).

    Polls the AgentTask row every second and pushes status updates until
    the task reaches a terminal state (completed / failed) or 6 min timeout.

    Event format (JSON payload per SSE message):
        { "status": "...", "answer": "...", "tokens_used": 0,
          "cost_usd": "0.000000", "execution_time_s": null,
          "intermediate_steps": [], "error_message": "" }
    """
    from django.http import HttpResponse, JsonResponse

    # ── Authenticate: JWT Bearer token (header or ?token= query param) ────────
    user = None
    token_str = None

    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Bearer "):
        token_str = auth_header[7:].strip()
    if not token_str:
        token_str = request.GET.get("token", "")

    if token_str:
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication
            from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
            from rest_framework_simplejwt.tokens import UntypedToken

            jwt_auth = JWTAuthentication()
            validated = jwt_auth.get_validated_token(token_str.encode())
            user = jwt_auth.get_user(validated)
        except Exception:
            return JsonResponse({"error": "Invalid or expired token."}, status=401)
    else:
        # Fall back to session authentication (for same-origin requests)
        if request.user and request.user.is_authenticated:
            user = request.user
        else:
            return JsonResponse({"error": "Authentication required."}, status=401)

    # ── Validate task ownership ───────────────────────────────────────────────
    try:
        AgentTask.objects.get(id=task_id, user=user)
    except AgentTask.DoesNotExist:
        return JsonResponse({"error": "Agent task not found."}, status=404)

    # ── SSE generator ─────────────────────────────────────────────────────────
    def _event_stream():
        terminal = {AgentTask.TaskStatus.COMPLETED, AgentTask.TaskStatus.FAILED}
        poll_interval = 1.0
        max_polls = 360  # give up after 6 minutes

        for _ in range(max_polls):
            try:
                task_obj = AgentTask.objects.get(id=task_id, user=user)
            except AgentTask.DoesNotExist:
                payload = json.dumps({"error": "Task not found."})
                yield f"event: error\ndata: {payload}\n\n"
                return

            serializer = AgentTaskSerializer(task_obj)
            data = serializer.data
            result_data = data.get("result") or {}
            payload = json.dumps(
                {
                    "status": data.get("status"),
                    "answer": data.get("answer") or "",
                    "tokens_used": data.get("tokens_used", 0),
                    "cost_usd": str(data.get("cost_usd", "0.000000")),
                    "execution_time_s": data.get("execution_time_s"),
                    "intermediate_steps": data.get("intermediate_steps") or [],
                    "error_message": data.get("error_message") or "",
                    "completed_at": data.get("completed_at"),
                    "result": {
                        "download_url": result_data.get("download_url"),
                        "file_name": result_data.get("file_name"),
                        "file_path": result_data.get("file_path"),
                        "file_size_bytes": result_data.get("file_size_bytes"),
                        "file_list": result_data.get("file_list"),
                    },
                }
            )
            yield f"data: {payload}\n\n"

            if data.get("status") in terminal:
                yield "event: done\ndata: {}\n\n"
                return

            time.sleep(poll_interval)

        yield "event: timeout\ndata: {}\n\n"

    response = StreamingHttpResponse(
        streaming_content=_event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # disable Nginx buffering
    return response


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agent_health(request: Request) -> Response:
    """GET /api/v1/agents/health/ — executor health check."""
    try:
        from ai_engine.agents import get_executor

        executor = get_executor()
        health_data = executor.health()
        return Response(health_data)
    except Exception as exc:
        logger.error("Agent health check failed: %s", exc)
        return Response(
            {"status": "error", "error": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ── TASK-306-B2: Prompt Library endpoints ────────────────────────────────────

from .serializers import (  # noqa: E402 — local import after models
    PromptTemplateCreateSerializer,
    PromptTemplateListSerializer,
    PromptTemplateSerializer,
)


class PromptListCreateView(APIView):
    """
    GET  /api/v1/agents/prompts/  — list public prompts
    POST /api/v1/agents/prompts/  — create a new prompt (auth required)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        category = request.query_params.get("category", "").strip().lower()
        sort = request.query_params.get("sort", "popular")  # popular | newest

        qs = PromptTemplate.objects.filter(is_public=True).select_related("author")
        if category and category != "all":
            qs = qs.filter(category=category)
        if sort == "newest":
            qs = qs.order_by("-created_at")
        else:
            qs = qs.order_by("-upvotes", "-use_count", "-created_at")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = PromptTemplateListSerializer(
            page if page is not None else qs,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response({"success": True, "data": serializer.data})

    def post(self, request: Request) -> Response:
        serializer = PromptTemplateCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        prompt = serializer.save(author=request.user)
        return Response(
            {
                "success": True,
                "data": PromptTemplateSerializer(
                    prompt, context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PromptDetailView(APIView):
    """GET /api/v1/agents/prompts/{id}/ — get single prompt."""

    permission_classes = [IsAuthenticated]

    def _get_prompt(self, pk, user):
        try:
            p = PromptTemplate.objects.select_related("author").get(pk=pk)
        except PromptTemplate.DoesNotExist:
            return None
        if not p.is_public and p.author != user:
            return None
        return p

    def get(self, request: Request, pk) -> Response:
        prompt = self._get_prompt(pk, request.user)
        if not prompt:
            return Response({"success": False, "error": "Not found"}, status=404)
        return Response(
            {
                "success": True,
                "data": PromptTemplateSerializer(
                    prompt, context={"request": request}
                ).data,
            }
        )


class PromptUseView(APIView):
    """POST /api/v1/agents/prompts/{id}/use/ — increment use_count, return content."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk) -> Response:
        try:
            prompt = PromptTemplate.objects.get(pk=pk)
        except PromptTemplate.DoesNotExist:
            return Response({"success": False, "error": "Not found"}, status=404)
        if not prompt.is_public and prompt.author != request.user:
            return Response({"success": False, "error": "Not found"}, status=404)
        PromptTemplate.objects.filter(pk=pk).update(use_count=prompt.use_count + 1)
        return Response(
            {
                "success": True,
                "data": {"content": prompt.content, "title": prompt.title},
            }
        )


class PromptUpvoteView(APIView):
    """POST /api/v1/agents/prompts/{id}/upvote/ — toggle upvote."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk) -> Response:
        try:
            prompt = PromptTemplate.objects.get(pk=pk)
        except PromptTemplate.DoesNotExist:
            return Response({"success": False, "error": "Not found"}, status=404)
        existing = PromptUpvote.objects.filter(user=request.user, prompt=prompt).first()
        if existing:
            existing.delete()
            PromptTemplate.objects.filter(pk=pk).update(
                upvotes=max(0, prompt.upvotes - 1)
            )
            upvoted = False
        else:
            PromptUpvote.objects.create(user=request.user, prompt=prompt)
            PromptTemplate.objects.filter(pk=pk).update(upvotes=prompt.upvotes + 1)
            upvoted = True
        prompt.refresh_from_db()
        return Response(
            {"success": True, "data": {"upvoted": upvoted, "upvotes": prompt.upvotes}}
        )


class MyPromptsView(APIView):
    """GET /api/v1/agents/prompts/my/ — list user's own prompts."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = PromptTemplate.objects.filter(author=request.user).select_related("author")
        serializer = PromptTemplateSerializer(
            qs, many=True, context={"request": request}
        )
        return Response({"success": True, "data": serializer.data})


# ── TASK-601-B3: Research Session endpoints ───────────────────────────────────

from .models import ResearchSession  # noqa: E402


class ResearchSessionListCreateView(APIView):
    """
    GET  /api/v1/agents/research/  — list user's research sessions
    POST /api/v1/agents/research/  — start a new research session
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = ResearchSession.objects.filter(user=request.user).order_by("-created_at")[
            :20
        ]
        data = [
            {
                "id": str(s.id),
                "query": s.query,
                "status": s.status,
                "sub_questions": s.sub_questions,
                "created_at": s.created_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in qs
        ]
        return Response({"success": True, "data": data})

    def post(self, request: Request) -> Response:
        query = (request.data.get("query") or "").strip()
        if not query:
            return Response(
                {"success": False, "error": "query is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(query) > 2000:
            return Response(
                {"success": False, "error": "query too long (max 2000 chars)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = ResearchSession.objects.create(user=request.user, query=query)

        # Enqueue background research task (best-effort — no blocking)
        try:
            from apps.core.tasks import run_research_session  # noqa: PLC0415

            run_research_session.delay(str(session.id))
        except Exception as exc:
            logger.warning("Could not enqueue research task: %s", exc)

        return Response(
            {
                "success": True,
                "data": {
                    "id": str(session.id),
                    "query": session.query,
                    "status": session.status,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class ResearchSessionDetailView(APIView):
    """GET /api/v1/agents/research/{id}/ — get session status + report."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, pk) -> Response:
        try:
            session = ResearchSession.objects.get(pk=pk, user=request.user)
        except ResearchSession.DoesNotExist:
            return Response({"success": False, "error": "Not found"}, status=404)

        return Response(
            {
                "success": True,
                "data": {
                    "id": str(session.id),
                    "query": session.query,
                    "status": session.status,
                    "report": session.report,
                    "sources": session.sources,
                    "sub_questions": session.sub_questions,
                    "created_at": session.created_at.isoformat(),
                    "completed_at": (
                        session.completed_at.isoformat()
                        if session.completed_at
                        else None
                    ),
                },
            }
        )
