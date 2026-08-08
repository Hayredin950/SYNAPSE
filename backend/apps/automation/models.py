import uuid

from apps.users.models import User

from django.db import models


class AutomationWorkflow(models.Model):
    class TriggerType(models.TextChoices):
        SCHEDULE = "schedule", "Schedule"
        EVENT = "event", "Event"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        FAILED = "failed", "Failed"

    class EventType(models.TextChoices):
        NEW_ARTICLE = "new_article", "New Article Published"
        TRENDING_SPIKE = "trending_spike", "Trending Topic Spike"
        NEW_PAPER = "new_paper", "New Research Paper"
        NEW_REPO = "new_repo", "New Repository Trending"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workflows")
    # TASK-006-B4: scope workflows to an organization workspace
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="workflows",
        help_text="If set, this workflow belongs to an org workspace.",
    )
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    trigger_type = models.CharField(
        max_length=20, choices=TriggerType.choices, default=TriggerType.SCHEDULE
    )
    cron_expression = models.CharField(max_length=100, blank=True)
    # Event trigger config: {"event_type": "new_article", "filter": {"topic": "AI"}, "cooldown_minutes": 60}
    event_config = models.JSONField(default=dict, blank=True)
    actions = models.JSONField(default=list)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    run_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── TASK-604-B1: Automation Marketplace fields ──────────────────────────
    is_published = models.BooleanField(default=False)
    marketplace_title = models.CharField(max_length=200, blank=True)
    marketplace_description = models.TextField(blank=True)
    download_count = models.PositiveIntegerField(default=0)
    upvotes = models.PositiveIntegerField(default=0)
    price_cents = models.PositiveIntegerField(default=0)  # 0 = free
    author_revenue_share = models.FloatField(default=0.7)  # 70%

    class Meta:
        db_table = "automation_workflows"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.name}"


class WorkflowRun(models.Model):
    class RunStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(
        AutomationWorkflow, on_delete=models.CASCADE, related_name="runs"
    )
    status = models.CharField(
        max_length=20, choices=RunStatus.choices, default=RunStatus.PENDING
    )
    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True)
    trigger_event = models.JSONField(
        default=dict, blank=True
    )  # event payload that caused this run
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "workflow_runs"
        ordering = ["-started_at"]
