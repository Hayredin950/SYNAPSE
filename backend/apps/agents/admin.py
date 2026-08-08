"""
backend.apps.agents.admin
~~~~~~~~~~~~~~~~~~~~~~~~~
Django admin configuration for AgentTask.

Phase 5.1 — Agent Framework (Week 13)
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import AgentTask


@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "task_type",
        "status_badge",
        "tokens_used",
        "cost_usd",
        "created_at",
        "completed_at",
    ]
    list_filter = ["status", "task_type", "created_at"]
    search_fields = ["user__email", "prompt", "task_type", "id"]
    readonly_fields = [
        "id",
        "user",
        "celery_task_id",
        "tokens_used",
        "cost_usd",
        "result",
        "error_message",
        "created_at",
        "completed_at",
    ]
    ordering = ["-created_at"]
    list_per_page = 50

    fieldsets = (
        (
            "Task Info",
            {
                "fields": ("id", "user", "task_type", "prompt", "status"),
            },
        ),
        (
            "Execution",
            {
                "fields": (
                    "celery_task_id",
                    "tokens_used",
                    "cost_usd",
                    "created_at",
                    "completed_at",
                ),
            },
        ),
        (
            "Result",
            {
                "fields": ("result", "error_message"),
                "classes": ("collapse",),
            },
        ),
    )

    def status_badge(self, obj: AgentTask) -> str:
        colours = {
            "pending": "#f59e0b",
            "processing": "#3b82f6",
            "completed": "#10b981",
            "failed": "#ef4444",
        }
        colour = colours.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            colour,
            obj.status.upper(),
        )

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"
