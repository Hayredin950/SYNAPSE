from django.contrib import admin

from .models import Membership, Organization, OrganizationInvite


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fields = ("user", "role", "is_active", "joined_at")
    readonly_fields = ("joined_at",)


class InviteInline(admin.TabularInline):
    model = OrganizationInvite
    extra = 0
    fields = ("email", "role", "is_accepted", "created_at")
    readonly_fields = ("created_at", "token")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "plan", "owner", "member_count", "created_at")
    list_filter = ("plan",)
    search_fields = ("name", "slug", "owner__email")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [MembershipInline, InviteInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active")
    search_fields = ("user__email", "organization__name")


@admin.register(OrganizationInvite)
class OrganizationInviteAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "role", "is_accepted", "created_at")
    list_filter = ("is_accepted",)
    search_fields = ("email", "organization__name")
    readonly_fields = ("token", "created_at")
