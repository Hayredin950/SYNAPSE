"""
Django admin configuration for the Automation app.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import AutomationWorkflow, WorkflowRun


class WorkflowRunInline(admin.TabularInline):
    model = WorkflowRun
    extra = 0
    readonly_fields = ["id", "status", "started_at", "completed_at", "error_message"]
    fields = ["status", "started_at", "completed_at", "error_message"]
    ordering = ["-started_at"]
    max_num = 10


@admin.register(AutomationWorkflow)
class AutomationWorkflowAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "user",
        "trigger_type",
        "status_badge",
        "is_active",
        "cron_expression",
        "run_count",
        "last_run_at",
        "created_at",
    ]
    list_filter = ["trigger_type", "is_active", "status", "created_at"]
    search_fields = ["name", "description", "user__email"]
    readonly_fields = [
        "id",
        "run_count",
        "last_run_at",
        "next_run_at",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]
    inlines = [WorkflowRunInline]

    fieldsets = (
        (
            "Basic Info",
            {
                "fields": ("id", "user", "name", "description"),
            },
        ),
        (
            "Trigger",
            {
                "fields": ("trigger_type", "cron_expression"),
            },
        ),
        (
            "Actions",
            {
                "fields": ("actions",),
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "status",
                    "run_count",
                    "last_run_at",
                    "next_run_at",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def status_badge(self, obj):
        colours = {
            "active": "green",
            "paused": "orange",
            "failed": "red",
        }
        colour = colours.get(obj.status, "grey")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colour,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"


@admin.register(WorkflowRun)
class WorkflowRunAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "workflow",
        "status",
        "started_at",
        "completed_at",
        "error_message",
    ]
    list_filter = ["status", "started_at"]
    search_fields = ["workflow__name", "workflow__user__email"]
    readonly_fields = [
        "id",
        "workflow",
        "status",
        "started_at",
        "completed_at",
        "result",
        "error_message",
    ]
    ordering = ["-started_at"]
