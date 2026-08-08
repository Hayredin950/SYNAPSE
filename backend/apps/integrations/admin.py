from django.contrib import admin

from .models import GoogleDriveToken


@admin.register(GoogleDriveToken)
class GoogleDriveTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "google_email", "connected_at", "updated_at"]
    list_filter = ["connected_at"]
    search_fields = ["user__email", "google_email"]
    readonly_fields = ["id", "connected_at", "updated_at", "encrypted_credentials"]
