"""
backend.apps.documents.admin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Django admin for GeneratedDocument.

Phase 5.2 — Document Generation (Week 14)
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import GeneratedDocument


@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "title",
        "doc_type_badge",
        "file_size_kb",
        "created_at",
    ]
    list_filter = ["doc_type", "created_at"]
    search_fields = ["user__email", "title", "agent_prompt", "id"]
    readonly_fields = [
        "id",
        "user",
        "title",
        "doc_type",
        "file_path",
        "cloud_url",
        "file_size_bytes",
        "agent_prompt",
        "metadata",
        "created_at",
    ]
    ordering = ["-created_at"]
    list_per_page = 50

    fieldsets = (
        (
            "Document Info",
            {
                "fields": ("id", "user", "title", "doc_type"),
            },
        ),
        (
            "File",
            {
                "fields": ("file_path", "cloud_url", "file_size_bytes"),
            },
        ),
        (
            "Generation",
            {
                "fields": ("agent_prompt", "metadata", "created_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def doc_type_badge(self, obj: GeneratedDocument) -> str:
        colours = {
            "pdf": "#EF4444",
            "ppt": "#F59E0B",
            "word": "#3B82F6",
            "markdown": "#10B981",
        }
        colour = colours.get(obj.doc_type, "#6B7280")
        label = obj.get_doc_type_display()
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            colour,
            label,
        )

    doc_type_badge.short_description = "Type"
    doc_type_badge.admin_order_field = "doc_type"

    def file_size_kb(self, obj: GeneratedDocument) -> str:
        if obj.file_size_bytes:
            return f"{obj.file_size_bytes / 1024:.1f} KB"
        return "—"

    file_size_kb.short_description = "Size"
