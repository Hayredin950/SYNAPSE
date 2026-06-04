"""
Django admin configuration for the Notifications app.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "user",
        "notif_type",
        "read_badge",
        "created_at",
    ]
    list_filter = ["notif_type", "is_read", "created_at"]
    search_fields = ["title", "message", "user__email"]
    readonly_fields = ["id", "created_at"]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Notification",
            {
                "fields": ("id", "user", "title", "message", "notif_type"),
            },
        ),
        (
            "State",
            {
                "fields": ("is_read", "metadata"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at",),
                "classes": ("collapse",),
            },
        ),
    )

    def read_badge(self, obj):
        if obj.is_read:
            return format_html('<span style="color:grey;">Read</span>')
        return format_html('<span style="color:green;font-weight:bold;">Unread</span>')

    read_badge.short_description = "Read Status"

    actions = ["mark_as_read"]

    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"{updated} notifications marked as read.")

    mark_as_read.short_description = "Mark selected notifications as read"
