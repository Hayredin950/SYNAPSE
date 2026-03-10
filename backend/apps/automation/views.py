"""
Views for the Automation app.

Endpoints:
  CRUD        /api/v1/automation/workflows/
  Trigger     /api/v1/automation/workflows/<id>/trigger/
  Toggle      /api/v1/automation/workflows/<id>/toggle/
  Runs        /api/v1/automation/workflows/<id>/runs/
  Run detail  /api/v1/automation/runs/<id>/
  Run status  /api/v1/automation/runs/<id>/status/   ← live SSE polling
  Event hook  /api/v1/automation/events/trigger/     ← internal event dispatch
"""

import json
import logging
import time

from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AutomationWorkflow, WorkflowRun
from .serializers import (
    AutomationWorkflowListSerializer,
    AutomationWorkflowSerializer,
    WorkflowRunSerializer,
    get_action_schemas,
)

logger = logging.getLogger(__name__)


# ── CRUD ───────────────────────────────────────────────────────────────────────


class WorkflowListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/automation/workflows/   — list current user's workflows
    POST /api/v1/automation/workflows/   — create a new workflow
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return AutomationWorkflowListSerializer
        return AutomationWorkflowSerializer

    def get_queryset(self):
        return AutomationWorkflow.objects.filter(
            user=self.request.user
        ).prefetch_related("runs")

    def perform_create(self, serializer):
        workflow = serializer.save(user=self.request.user)
        if workflow.trigger_type == AutomationWorkflow.TriggerType.SCHEDULE:
            _register_workflow_beat(workflow)
        logger.info(
            "Workflow created: %s (%s) by %s",
            workflow.id,
            workflow.name,
            self.request.user.email,
        )


class WorkflowRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET / PUT / PATCH / DELETE /api/v1/automation/workflows/<id>/
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AutomationWorkflowSerializer

    def get_queryset(self):
        return AutomationWorkflow.objects.filter(
            user=self.request.user
        ).prefetch_related("runs")

    def perform_update(self, serializer):
        workflow = serializer.save()
        if workflow.trigger_type == AutomationWorkflow.TriggerType.SCHEDULE:
            _register_workflow_beat(workflow)
        logger.info("Workflow updated: %s (%s)", workflow.id, workflow.name)

    def perform_destroy(self, instance):
        _unregister_workflow_beat(instance)
        instance.delete()
        logger.info("Workflow deleted: %s (%s)", instance.id, instance.name)


# ── Trigger / Toggle ───────────────────────────────────────────────────────────


class WorkflowTriggerView(APIView):
    """
    POST /api/v1/automation/workflows/<id>/trigger/
    Manually trigger a workflow execution and return the run_id immediately.

    The WorkflowRun record is created synchronously here (before Celery picks
    up the task) so the frontend can start polling /runs/<run_id>/status/
    straight away without any race condition.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            workflow = AutomationWorkflow.objects.get(pk=pk, user=request.user)
        except AutomationWorkflow.DoesNotExist:
            return Response(
                {"detail": "Workflow not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not workflow.is_active:
            return Response(
                {"detail": "Workflow is not active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .models import WorkflowRun
        from .tasks import execute_workflow

        # Create the run record first so the frontend has a run_id to poll
        # immediately — no race condition waiting for Celery to create it.
        run = WorkflowRun.objects.create(
            workflow=workflow,
            status=WorkflowRun.RunStatus.PENDING,
            trigger_event={},
        )

        # ── Worker-availability detection ─────────────────────────────────────
        # On managed hosts (e.g. Render) it is common to have Redis up but no
        # Celery worker running. In that case `apply_async` succeeds (it just
        # enqueues to Redis), the task sits in the queue forever, and the run
        # is permanently stuck in PENDING. Probe for a live worker first and
        # fall back to a synchronous execution if none are listening.
        from config.celery import app as _celery_app

        workers_online = False
        try:
            ping_result = _celery_app.control.inspect(timeout=1.0).ping()
            workers_online = bool(ping_result)
        except Exception as ping_err:
            logger.warning("Celery worker ping failed: %s", ping_err)

        task_id = None
        if workers_online:
            try:
                task = execute_workflow.apply_async(
                    args=[str(workflow.id)],
                    kwargs={"run_id": str(run.id)},
                )
                # Persist the celery task id on the run record
                run.celery_task_id = task.id
                run.save(update_fields=["celery_task_id"])
                task_id = task.id
            except Exception as celery_error:
                # Broker reachable but enqueue failed for another reason —
                # still fall back to sync so the user actually gets results.
                logger.warning(
                    "Celery enqueue failed, running workflow synchronously: %s",
                    celery_error,
                )
                workers_online = False  # force sync branch below

        if not workers_online:
            # No live Celery worker — run synchronously inside the request so
            # the workflow actually executes. This is slower but guarantees
            # behaviour on hosts that haven't deployed a worker service yet.
            logger.warning(
                "No Celery worker responding; running workflow %s synchronously.",
                workflow.id,
            )
            run.celery_task_id = "sync_fallback"
            run.save(update_fields=["celery_task_id"])
            task_id = run.celery_task_id
            try:
                execute_workflow(str(workflow.id), run_id=str(run.id))
            except Exception as exec_err:
                # Surface execution errors on the run record so the UI shows them
                logger.exception("Synchronous workflow execution failed.")
                run.refresh_from_db()
                if run.status not in ("success", "failed"):
                    run.status = "failed"
                    run.error_message = str(exec_err)[:500]
                    run.save(update_fields=["status", "error_message"])

        logger.info(
            "Workflow %s manually triggered by %s. run=%s celery_task=%s",
            workflow.id,
            request.user.email,
            run.id,
            task_id,
        )
        return Response(
            {
                "detail": "Workflow triggered successfully.",
                "workflow_id": str(workflow.id),
                "run_id": str(run.id),
                "celery_task_id": task_id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class WorkflowToggleView(APIView):
    """
    POST /api/v1/automation/workflows/<id>/toggle/
    Pause / resume a workflow.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            workflow = AutomationWorkflow.objects.get(pk=pk, user=request.user)
        except AutomationWorkflow.DoesNotExist:
            return Response(
                {"detail": "Workflow not found."}, status=status.HTTP_404_NOT_FOUND
            )

        workflow.is_active = not workflow.is_active
        new_status = (
            AutomationWorkflow.Status.ACTIVE
            if workflow.is_active
            else AutomationWorkflow.Status.PAUSED
        )
        workflow.status = new_status
        workflow.save(update_fields=["is_active", "status", "updated_at"])

        # Keep Celery Beat in sync
        if workflow.trigger_type == AutomationWorkflow.TriggerType.SCHEDULE:
            _register_workflow_beat(workflow)

        logger.info(
            "Workflow %s toggled to %s by %s",
            workflow.id,
            "active" if workflow.is_active else "paused",
            request.user.email,
        )
        return Response(
            {
                "detail": f"Workflow {'activated' if workflow.is_active else 'paused'}.",
                "is_active": workflow.is_active,
                "status": workflow.status,
            }
        )


# ── Run history ────────────────────────────────────────────────────────────────


class WorkflowRunListView(generics.ListAPIView):
    """GET /api/v1/automation/workflows/<id>/runs/"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkflowRunSerializer

    def get_queryset(self):
        return WorkflowRun.objects.filter(
            workflow__id=self.kwargs["pk"],
            workflow__user=self.request.user,
        )


class WorkflowRunDetailView(generics.RetrieveAPIView):
    """GET /api/v1/automation/runs/<id>/"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkflowRunSerializer

    def get_queryset(self):
        return WorkflowRun.objects.filter(workflow__user=self.request.user)


# ── Live run status (SSE + JSON polling) ───────────────────────────────────────


class WorkflowRunStatusView(APIView):
    """
    GET /api/v1/automation/runs/<id>/status/

    Returns current status of a WorkflowRun as JSON.
    If ?stream=1 is passed, uses Server-Sent Events to push updates every
    2 seconds until the run completes (or 5 minutes elapses).
    The frontend can simply poll this endpoint every 2s for a simpler approach.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            run = WorkflowRun.objects.get(pk=pk, workflow__user=request.user)
        except WorkflowRun.DoesNotExist:
            return Response(
                {"detail": "Run not found."}, status=status.HTTP_404_NOT_FOUND
            )

        use_sse = request.GET.get("stream", "0") == "1"

        if use_sse:
            return self._sse_stream(request, run)

        return Response(WorkflowRunSerializer(run).data)

    def _sse_stream(self, request, run):
        """Stream run status via Server-Sent Events until completion."""

        def event_generator():
            run_id = str(run.id)
            deadline = time.time() + 300  # 5 min hard cap
            terminal = {WorkflowRun.RunStatus.SUCCESS, WorkflowRun.RunStatus.FAILED}
            poll_interval = 2  # seconds

            while time.time() < deadline:
                try:
                    fresh = WorkflowRun.objects.get(pk=run_id)
                    data = WorkflowRunSerializer(fresh).data
                    yield f"data: {json.dumps(data)}\n\n"
                    if fresh.status in terminal:
                        yield "event: done\ndata: {}\n\n"
                        break
                except WorkflowRun.DoesNotExist:
                    yield f"data: {json.dumps({'error': 'run not found'})}\n\n"
                    break
                except Exception as exc:
                    yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                    break

                time.sleep(poll_interval)

        response = StreamingHttpResponse(
            event_generator(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


# ── Internal event webhook ─────────────────────────────────────────────────────


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def trigger_event_view(request):
    """
    POST /api/v1/automation/events/trigger/

    Body: { "event_type": "new_article", "payload": { ... } }

    Dispatches the event to all matching event-triggered workflows.
    Used internally by signals/tasks when system events occur.
    Also callable by admin users for manual testing.
    """
    event_type = request.data.get("event_type", "")
    payload = request.data.get("payload", {})

    if not event_type:
        return Response(
            {"detail": "event_type is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    valid_events = [c[0] for c in AutomationWorkflow.EventType.choices]
    if event_type not in valid_events:
        return Response(
            {"detail": f"Invalid event_type. Valid: {valid_events}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from .tasks import dispatch_event_trigger

    task = dispatch_event_trigger.delay(event_type, payload)

    return Response(
        {
            "detail": "Event dispatched.",
            "event_type": event_type,
            "celery_task_id": task.id,
        },
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def action_schemas_view(request):
    """
    GET /api/v1/automation/action-schemas/
    Returns parameter schemas for all action types (for the UI parameter editor).
    """
    return Response(get_action_schemas())


# ── Beat registration helpers ──────────────────────────────────────────────────


def _register_workflow_beat(workflow: AutomationWorkflow) -> None:
    """Register or update a PeriodicTask in django-celery-beat for a scheduled workflow."""
    try:
        import json

        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        if not workflow.cron_expression:
            return

        parts = workflow.cron_expression.strip().split()
        if len(parts) != 5:
            return

        minute, hour, day_of_month, month_of_year, day_of_week = parts

        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            day_of_week=day_of_week,
        )

        task_name = f"workflow-{workflow.id}"
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "crontab": schedule,
                "task": "apps.automation.tasks.execute_workflow",
                "args": json.dumps([str(workflow.id)]),
                "kwargs": json.dumps({}),
                "enabled": workflow.is_active,
            },
        )
        logger.info("Registered Celery Beat task: %s", task_name)
    except Exception as exc:
        logger.warning(
            "Failed to register beat task for workflow %s: %s", workflow.id, exc
        )


def _unregister_workflow_beat(workflow: AutomationWorkflow) -> None:
    """Remove the PeriodicTask associated with a workflow."""
    try:
        from django_celery_beat.models import PeriodicTask

        task_name = f"workflow-{workflow.id}"
        PeriodicTask.objects.filter(name=task_name).delete()
        logger.info("Unregistered Celery Beat task: %s", task_name)
    except Exception as exc:
        logger.warning(
            "Failed to unregister beat task for workflow %s: %s", workflow.id, exc
        )


# ── Workflow Templates ─────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def list_templates_view(request):
    """
    GET /api/v1/automation/templates/
    Returns all pre-built workflow templates.
    """
    from .templates import get_all_templates

    return Response(get_all_templates())


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def clone_template_view(request, template_id: str):
    """
    POST /api/v1/automation/templates/<template_id>/clone/
    Clone a workflow template for the current user.
    Body: { "name": "My Custom Name" }  (optional, defaults to template name)
    """
    from .templates import get_template

    template = get_template(template_id)
    if not template:
        return Response(
            {"detail": "Template not found."}, status=status.HTTP_404_NOT_FOUND
        )

    custom_name = request.data.get("name", template["name"])
    payload = {
        "name": custom_name,
        "description": template["description"],
        "trigger_type": template["trigger_type"],
        "cron_expression": template.get("cron_expression", ""),
        "event_config": template.get("event_config", {}),
        "actions": template["actions"],
    }

    serializer = AutomationWorkflowSerializer(
        data=payload, context={"request": request}
    )
    if serializer.is_valid():
        workflow = serializer.save(user=request.user)
        if workflow.trigger_type == AutomationWorkflow.TriggerType.SCHEDULE:
            _register_workflow_beat(workflow)
        logger.info(
            "Template '%s' cloned as workflow %s by %s",
            template_id,
            workflow.id,
            request.user.email,
        )
        return Response(
            AutomationWorkflowSerializer(workflow, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Scheduled Task Management ──────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def list_schedule_view(request):
    """
    GET /api/v1/automation/schedule/
    Returns all PeriodicTasks for the current user's workflows.
    """
    try:
        import json

        from django_celery_beat.models import PeriodicTask

        # Get all workflow IDs for this user
        user_wf_ids = list(
            AutomationWorkflow.objects.filter(user=request.user).values_list(
                "id", flat=True
            )
        )
        task_names = [f"workflow-{wf_id}" for wf_id in user_wf_ids]
        tasks = PeriodicTask.objects.filter(name__in=task_names).select_related(
            "crontab"
        )

        result = []
        for task in tasks:
            wf_id_str = task.name.replace("workflow-", "")
            try:
                wf = AutomationWorkflow.objects.get(id=wf_id_str, user=request.user)
            except AutomationWorkflow.DoesNotExist:
                continue

            result.append(
                {
                    "task_name": task.name,
                    "workflow_id": str(wf.id),
                    "workflow_name": wf.name,
                    "cron": str(task.crontab) if task.crontab else None,
                    "cron_expression": wf.cron_expression,
                    "enabled": task.enabled,
                    "last_run_at": task.last_run_at,
                    "total_run_count": task.total_run_count,
                    "next_run": str(task.crontab) if task.crontab else None,
                }
            )

        return Response(result)
    except Exception as exc:
        logger.warning("list_schedule_view error: %s", exc)
        return Response(
            {"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def toggle_schedule_view(request, pk):
    """
    POST /api/v1/automation/schedule/<workflow_id>/toggle/
    Enable or disable the Celery Beat periodic task for a workflow.
    """
    try:
        workflow = AutomationWorkflow.objects.get(pk=pk, user=request.user)
    except AutomationWorkflow.DoesNotExist:
        return Response(
            {"detail": "Workflow not found."}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        from django_celery_beat.models import PeriodicTask

        task = PeriodicTask.objects.get(name=f"workflow-{workflow.id}")
        task.enabled = not task.enabled
        task.save(update_fields=["enabled"])
        return Response({"enabled": task.enabled, "workflow_id": str(workflow.id)})
    except Exception as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


# ── Workflow Analytics ─────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def workflow_analytics_view(request):
    """
    GET /api/v1/automation/analytics/

    Query params:
      days  — lookback window in days (default 30, max 365)

    Returns aggregated analytics for the current user's workflows:
      - runs_over_time:    daily run counts (success/failed) for the last N days
      - success_rate:      overall percentage of successful runs
      - action_distribution: counts per action type across all workflows
      - top_workflows:    workflows ranked by run count
      - total_stats:      summary totals
    """
    import json
    from datetime import timedelta

    from django.db.models import Count, Q
    from django.utils import timezone

    try:
        days = min(int(request.GET.get("days", 30)), 365)
    except (ValueError, TypeError):
        days = 30

    since = timezone.now() - timedelta(days=days)

    # User's workflows
    user_workflows = AutomationWorkflow.objects.filter(user=request.user)
    workflow_ids = list(user_workflows.values_list("id", flat=True))

    # Runs in window
    runs_qs = WorkflowRun.objects.filter(
        workflow_id__in=workflow_ids,
        started_at__gte=since,
    )

    # ── Runs over time (daily buckets) ─────────────────────────────────────
    from django.db.models.functions import TruncDate

    daily = (
        runs_qs.annotate(date=TruncDate("started_at"))
        .values("date", "status")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    # Build a full date range so gaps appear as 0
    date_map: dict = {}
    for i in range(days):
        day = (since + timedelta(days=i + 1)).date()
        date_map[str(day)] = {"date": str(day), "success": 0, "failed": 0, "total": 0}

    for row in daily:
        key = str(row["date"])
        if key not in date_map:
            date_map[key] = {"date": key, "success": 0, "failed": 0, "total": 0}
        if row["status"] == "success":
            date_map[key]["success"] += row["count"]
        elif row["status"] == "failed":
            date_map[key]["failed"] += row["count"]
        date_map[key]["total"] += row["count"]

    runs_over_time = sorted(date_map.values(), key=lambda x: x["date"])

    # ── Success rate ───────────────────────────────────────────────────────
    total_runs = runs_qs.count()
    success_runs = runs_qs.filter(status="success").count()
    failed_runs = runs_qs.filter(status="failed").count()
    success_rate = round(success_runs / total_runs * 100, 1) if total_runs else 0.0

    # ── Action distribution (across all workflows in window) ───────────────
    action_counts: dict = {}
    for wf in user_workflows:
        for action in wf.actions or []:
            atype = action.get("type", "unknown")
            action_counts[atype] = action_counts.get(atype, 0) + 1

    action_distribution = [
        {"action": k, "count": v, "label": k.replace("_", " ").title()}
        for k, v in sorted(action_counts.items(), key=lambda x: -x[1])
    ]

    # ── Top workflows by run count ─────────────────────────────────────────
    top_workflows_qs = (
        runs_qs.values("workflow_id", "workflow__name")
        .annotate(
            total=Count("id"),
            success=Count("id", filter=Q(status="success")),
            failed=Count("id", filter=Q(status="failed")),
        )
        .order_by("-total")[:5]
    )
    top_workflows = [
        {
            "workflow_id": str(row["workflow_id"]),
            "name": row["workflow__name"],
            "total": row["total"],
            "success": row["success"],
            "failed": row["failed"],
            "success_rate": (
                round(row["success"] / row["total"] * 100, 1) if row["total"] else 0.0
            ),
        }
        for row in top_workflows_qs
    ]

    # ── Average duration ───────────────────────────────────────────────────
    completed = runs_qs.filter(completed_at__isnull=False)
    avg_duration = None
    if completed.exists():
        from django.db.models import Avg, DurationField, ExpressionWrapper, F

        avg_expr = completed.annotate(
            dur=ExpressionWrapper(
                F("completed_at") - F("started_at"), output_field=DurationField()
            )
        ).aggregate(avg=Avg("dur"))
        d = avg_expr.get("avg")
        if d:
            avg_duration = round(d.total_seconds(), 1)

    return Response(
        {
            "period_days": days,
            "total_stats": {
                "total_workflows": user_workflows.count(),
                "active_workflows": user_workflows.filter(is_active=True).count(),
                "total_runs": total_runs,
                "success_runs": success_runs,
                "failed_runs": failed_runs,
                "success_rate": success_rate,
                "avg_duration_seconds": avg_duration,
            },
            "runs_over_time": runs_over_time,
            "action_distribution": action_distribution,
            "top_workflows": top_workflows,
        }
    )


# ── TASK-604-B2: Automation Marketplace views ─────────────────────────────────


class MarketplaceListView(APIView):
    """GET /api/v1/automation/marketplace/ — list published workflow templates."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = (
            AutomationWorkflow.objects.filter(is_published=True)
            .select_related("user")
            .order_by("-upvotes", "-download_count")
        )
        category = request.query_params.get("category", "")
        free = request.query_params.get("free", "")
        if free == "true":
            qs = qs.filter(price_cents=0)
        data = [
            {
                "id": str(w.id),
                "title": w.marketplace_title or w.name,
                "description": w.marketplace_description or w.description,
                "author": w.user.get_full_name() or w.user.email,
                "download_count": w.download_count,
                "upvotes": w.upvotes,
                "price_cents": w.price_cents,
                "trigger_type": w.trigger_type,
                "created_at": w.created_at.isoformat(),
            }
            for w in qs[:50]
        ]
        return Response({"success": True, "data": data})


class MarketplaceDetailView(APIView):
    """GET /api/v1/automation/marketplace/{id}/ — template detail + preview."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            w = AutomationWorkflow.objects.select_related("user").get(
                pk=pk, is_published=True
            )
        except AutomationWorkflow.DoesNotExist:
            return Response({"success": False, "error": "Not found"}, status=404)
        return Response(
            {
                "success": True,
                "data": {
                    "id": str(w.id),
                    "title": w.marketplace_title or w.name,
                    "description": w.marketplace_description or w.description,
                    "author": w.user.get_full_name() or w.user.email,
                    "actions": w.actions,
                    "trigger_type": w.trigger_type,
                    "download_count": w.download_count,
                    "upvotes": w.upvotes,
                    "price_cents": w.price_cents,
                },
            }
        )


class MarketplaceInstallView(APIView):
    """POST /api/v1/automation/marketplace/{id}/install/ — clone to user's workspace."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            source = AutomationWorkflow.objects.get(pk=pk, is_published=True)
        except AutomationWorkflow.DoesNotExist:
            return Response({"success": False, "error": "Not found"}, status=404)
        clone = AutomationWorkflow.objects.create(
            user=request.user,
            name=f"{source.marketplace_title or source.name} (copy)",
            description=source.marketplace_description or source.description,
            trigger_type=source.trigger_type,
            cron_expression=source.cron_expression,
            event_config=source.event_config,
            actions=source.actions,
            is_published=False,
        )
        AutomationWorkflow.objects.filter(pk=pk).update(
            download_count=source.download_count + 1
        )
        return Response(
            {"success": True, "data": {"id": str(clone.id), "name": clone.name}},
            status=201,
        )


class MarketplacePublishView(APIView):
    """POST /api/v1/automation/marketplace/{id}/publish/ — publish user's workflow."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            w = AutomationWorkflow.objects.get(pk=pk, user=request.user)
        except AutomationWorkflow.DoesNotExist:
            return Response({"success": False, "error": "Not found"}, status=404)
        title = (request.data.get("title") or w.name).strip()
        desc = (request.data.get("description") or "").strip()
        if not title:
            return Response(
                {"success": False, "error": "title is required"}, status=400
            )
        w.marketplace_title = title
        w.marketplace_description = desc
        w.is_published = True
        w.save(
            update_fields=[
                "marketplace_title",
                "marketplace_description",
                "is_published",
            ]
        )
        return Response(
            {"success": True, "data": {"id": str(w.id), "is_published": True}}
        )


class MarketplaceUpvoteView(APIView):
    """POST /api/v1/automation/marketplace/{id}/upvote/ — increment upvote count."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            w = AutomationWorkflow.objects.get(pk=pk, is_published=True)
        except AutomationWorkflow.DoesNotExist:
            return Response({"success": False, "error": "Not found"}, status=404)
        AutomationWorkflow.objects.filter(pk=pk).update(upvotes=w.upvotes + 1)
        w.refresh_from_db()
        return Response({"success": True, "data": {"upvotes": w.upvotes}})
