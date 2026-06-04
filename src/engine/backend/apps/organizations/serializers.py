"""
backend.apps.organizations.serializers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DRF serializers for Organizations, Memberships, and Invites.

TASK-006
"""

from __future__ import annotations

from rest_framework import serializers

from .models import Membership, Organization, OrganizationInvite


class MembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.SerializerMethodField()
    user_avatar_url = serializers.URLField(
        source="user.avatar_url", read_only=True, default=None
    )

    class Meta:
        model = Membership
        fields = [
            "id",
            "user",
            "user_email",
            "user_name",
            "user_avatar_url",
            "role",
            "is_active",
            "joined_at",
        ]
        read_only_fields = ["id", "joined_at"]

    def get_user_name(self, obj) -> str:
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email


class OrganizationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    member_count = serializers.IntegerField(read_only=True)
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "logo_url",
            "website",
            "plan",
            "owner",
            "owner_email",
            "member_count",
            "my_role",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "owner"]

    def get_my_role(self, obj) -> str | None:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.user_role(request.user)
        return None


class OrganizationDetailSerializer(OrganizationListSerializer):
    """Full serializer including members list."""

    members = MembershipSerializer(source="memberships", many=True, read_only=True)

    class Meta(OrganizationListSerializer.Meta):
        fields = OrganizationListSerializer.Meta.fields + ["members", "updated_at"]


class OrganizationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["name", "description", "logo_url", "website"]

    def validate_name(self, value: str) -> str:
        if len(value.strip()) < 2:
            raise serializers.ValidationError(
                "Organization name must be at least 2 characters."
            )
        return value.strip()


class InviteSerializer(serializers.ModelSerializer):
    invited_by_email = serializers.EmailField(source="invited_by.email", read_only=True)
    org_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = OrganizationInvite
        fields = [
            "id",
            "email",
            "role",
            "is_accepted",
            "accepted_at",
            "expires_at",
            "created_at",
            "invited_by_email",
            "org_name",
        ]
        read_only_fields = [
            "id",
            "is_accepted",
            "accepted_at",
            "created_at",
            "token",
            "invited_by_email",
            "org_name",
        ]


class InviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=["admin", "member", "viewer"],
        default="member",
    )


class OrgAuditLogSerializer(serializers.ModelSerializer):
    """TASK-006-B5: Read-only serializer for audit log entries."""

    actor_email = serializers.EmailField(
        source="actor.email", read_only=True, default=None
    )

    class Meta:
        from .models import OrgAuditLog

        model = OrgAuditLog
        fields = [
            "id",
            "action",
            "actor_email",
            "resource",
            "metadata",
            "ip_address",
            "timestamp",
        ]
        read_only_fields = fields
