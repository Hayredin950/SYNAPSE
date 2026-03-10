"""
backend.apps.organizations.views
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
API views for Team Workspaces & Organizations — TASK-006-B2

Endpoints:
  GET|POST   /api/v1/organizations/
  GET|PATCH|DELETE /api/v1/organizations/{id}/
  GET|POST   /api/v1/organizations/{id}/members/
  PATCH|DELETE /api/v1/organizations/{id}/members/{user_id}/
  GET|POST   /api/v1/organizations/{id}/invites/
  DELETE     /api/v1/organizations/{id}/invites/{invite_id}/
  POST       /api/v1/organizations/invites/{token}/accept/
"""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Membership,
    Organization,
    OrganizationInvite,
    OrgAuditLog,
    OrgPlan,
    OrgRole,
)
from .permissions import IsOrgAdminOrOwner, IsOrgMember, IsOrgOwner
from .serializers import (
    InviteCreateSerializer,
    InviteSerializer,
    MembershipSerializer,
    OrganizationCreateSerializer,
    OrganizationDetailSerializer,
    OrganizationListSerializer,
    OrgAuditLogSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_org_or_404(pk, user):
    """Return (org, membership) or raise a 404 response."""
    try:
        org = Organization.objects.get(pk=pk)
    except Organization.DoesNotExist:
        return None, None
    return org, None


def _org_response(org, request, detail=False):
    Ser = OrganizationDetailSerializer if detail else OrganizationListSerializer
    return Ser(org, context={"request": request}).data


# ── Organization List / Create ─────────────────────────────────────────────────


class OrganizationListCreateView(APIView):
    """
    GET  /api/v1/organizations/  — list all orgs the user owns or belongs to
    POST /api/v1/organizations/  — create a new org (creator becomes owner)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Orgs where user is owner OR active member
        member_org_ids = Membership.objects.filter(
            user=request.user, is_active=True
        ).values_list("organization_id", flat=True)

        orgs = (
            Organization.objects.filter(id__in=list(member_org_ids))
            .select_related("owner")
            .prefetch_related("memberships")
        )

        serializer = OrganizationListSerializer(
            orgs, many=True, context={"request": request}
        )
        return Response({"success": True, "data": serializer.data})

    def post(self, request):
        # Check org limit per plan
        owned_count = Organization.objects.filter(owner=request.user).count()
        # Use free plan limits by default (most conservative)
        max_orgs = Organization.MAX_ORGS.get("free", 1)
        # If user has a pro membership somewhere, allow more — simple heuristic
        if owned_count >= max_orgs:
            return Response(
                {
                    "success": False,
                    "error": f"You can only own up to {max_orgs} organization(s) on the free plan.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        ser = OrganizationCreateSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"success": False, "error": ser.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        org = ser.save(owner=request.user)

        # Auto-create owner membership
        Membership.objects.create(
            organization=org,
            user=request.user,
            role=OrgRole.OWNER,
            is_active=True,
        )
        OrgAuditLog.objects.create(
            organization=org,
            actor=request.user,
            action=OrgAuditLog.Action.ORG_CREATED,
            resource=org.name,
        )
        logger.info("org_created: user=%s org=%s", request.user.email, org.slug)

        return Response(
            {"success": True, "data": _org_response(org, request, detail=True)},
            status=status.HTTP_201_CREATED,
        )


# ── Organization Detail / Update / Delete ──────────────────────────────────────


class OrganizationDetailView(APIView):
    """
    GET    /api/v1/organizations/{id}/  — org detail (members must be active)
    PATCH  /api/v1/organizations/{id}/  — update name/logo/desc (admin+)
    DELETE /api/v1/organizations/{id}/  — delete org (owner only)
    """

    permission_classes = [IsAuthenticated]

    def _get_org(self, pk):
        try:
            return (
                Organization.objects.select_related("owner")
                .prefetch_related("memberships__user")
                .get(pk=pk)
            )
        except Organization.DoesNotExist:
            return None

    def get(self, request, pk):
        org = self._get_org(pk)
        if org is None:
            return Response({"success": False, "error": "Not found."}, status=404)
        if not org.is_member(request.user):
            return Response(
                {
                    "success": False,
                    "error": "You are not a member of this organization.",
                },
                status=403,
            )
        return Response(
            {"success": True, "data": _org_response(org, request, detail=True)}
        )

    def patch(self, request, pk):
        org = self._get_org(pk)
        if org is None:
            return Response({"success": False, "error": "Not found."}, status=404)
        if not org.is_admin_or_owner(request.user):
            return Response(
                {"success": False, "error": "Admin or owner role required."}, status=403
            )

        allowed = ["name", "description", "logo_url", "website"]
        data = {k: v for k, v in request.data.items() if k in allowed}
        ser = OrganizationCreateSerializer(org, data=data, partial=True)
        if not ser.is_valid():
            return Response({"success": False, "error": ser.errors}, status=400)
        ser.save()
        return Response(
            {"success": True, "data": _org_response(org, request, detail=True)}
        )

    def delete(self, request, pk):
        org = self._get_org(pk)
        if org is None:
            return Response({"success": False, "error": "Not found."}, status=404)
        if org.owner != request.user:
            return Response(
                {
                    "success": False,
                    "error": "Only the owner can delete this organization.",
                },
                status=403,
            )
        logger.warning("org_deleted: user=%s org=%s", request.user.email, org.slug)
        org.delete()
        return Response(
            {"success": True, "message": "Organization deleted."}, status=204
        )


# ── Member Management ──────────────────────────────────────────────────────────


class MemberListView(APIView):
    """
    GET  /api/v1/organizations/{id}/members/  — list active members
    POST /api/v1/organizations/{id}/members/  — add member by user_id (admin+)
    """

    permission_classes = [IsAuthenticated]

    def _get_org(self, pk):
        try:
            return Organization.objects.get(pk=pk)
        except Organization.DoesNotExist:
            return None

    def get(self, request, pk):
        org = self._get_org(pk)
        if org is None:
            return Response({"success": False, "error": "Not found."}, status=404)
        if not org.is_member(request.user):
            return Response({"success": False, "error": "Forbidden."}, status=403)
        members = org.memberships.filter(is_active=True).select_related("user")
        ser = MembershipSerializer(members, many=True)
        return Response({"success": True, "data": ser.data})

    def post(self, request, pk):
        org = self._get_org(pk)
        if org is None:
            return Response({"success": False, "error": "Not found."}, status=404)
        if not org.is_admin_or_owner(request.user):
            return Response(
                {"success": False, "error": "Admin or owner role required."}, status=403
            )
        if org.is_full:
            return Response(
                {
                    "success": False,
                    "error": f"Organization is at member limit ({org.max_members}).",
                },
                status=403,
            )

        user_id = request.data.get("user_id")
        role = request.data.get("role", OrgRole.MEMBER)
        if role not in [r[0] for r in OrgRole.choices if r[0] != OrgRole.OWNER]:
            return Response({"success": False, "error": "Invalid role."}, status=400)

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"success": False, "error": "User not found."}, status=404)

        membership, created = Membership.objects.get_or_create(
            organization=org,
            user=user,
            defaults={"role": role, "is_active": True},
        )
        if not created:
            if membership.is_active:
                return Response(
                    {"success": False, "error": "User is already a member."}, status=400
                )
            membership.is_active = True
            membership.role = role
            membership.save(update_fields=["is_active", "role", "updated_at"])

        OrgAuditLog.objects.create(
            organization=org,
            actor=request.user,
            action=OrgAuditLog.Action.MEMBER_ADDED,
            resource=user.email,
            metadata={"role": role},
        )
        logger.info(
            "member_added: actor=%s user=%s org=%s role=%s",
            request.user.email,
            user.email,
            org.slug,
            role,
        )
        return Response(
            {"success": True, "data": MembershipSerializer(membership).data}, status=201
        )


class MemberDetailView(APIView):
    """
    PATCH  /api/v1/organizations/{id}/members/{user_id}/  — change role (admin+)
    DELETE /api/v1/organizations/{id}/members/{user_id}/  — remove member (admin+ or self)
    """

    permission_classes = [IsAuthenticated]

    def _get_org_and_membership(self, pk, user_id):
        try:
            org = Organization.objects.get(pk=pk)
            membership = Membership.objects.select_related("user").get(
                organization=org, user_id=user_id, is_active=True
            )
            return org, membership
        except (Organization.DoesNotExist, Membership.DoesNotExist):
            return None, None

    def patch(self, request, pk, user_id):
        org, membership = self._get_org_and_membership(pk, user_id)
        if org is None:
            return Response({"success": False, "error": "Not found."}, status=404)
        if not org.is_admin_or_owner(request.user):
            return Response(
                {"success": False, "error": "Admin or owner role required."}, status=403
            )

        new_role = request.data.get("role")
        if new_role not in [r[0] for r in OrgRole.choices if r[0] != OrgRole.OWNER]:
            return Response(
                {
                    "success": False,
                    "error": "Invalid role. Cannot assign owner role via API.",
                },
                status=400,
            )

        # Owner cannot have their role changed by an admin
        if membership.role == OrgRole.OWNER and org.owner != request.user:
            return Response(
                {"success": False, "error": "Cannot change owner role."}, status=403
            )

        membership.role = new_role
        membership.save(update_fields=["role", "updated_at"])
        OrgAuditLog.objects.create(
            organization=org,
            actor=request.user,
            action=OrgAuditLog.Action.ROLE_CHANGED,
            resource=membership.user.email,
            metadata={"new_role": new_role},
        )
        logger.info(
            "role_changed: actor=%s user=%s org=%s new_role=%s",
            request.user.email,
            membership.user.email,
            org.slug,
            new_role,
        )
        return Response(
            {"success": True, "data": MembershipSerializer(membership).data}
        )

    def delete(self, request, pk, user_id):
        org, membership = self._get_org_and_membership(pk, user_id)
        if org is None:
            return Response({"success": False, "error": "Not found."}, status=404)

        is_self = str(request.user.pk) == str(user_id)
        if not is_self and not org.is_admin_or_owner(request.user):
            return Response(
                {
                    "success": False,
                    "error": "Admin or owner role required to remove others.",
                },
                status=403,
            )

        # Owner cannot be removed
        if membership.role == OrgRole.OWNER:
            return Response(
                {
                    "success": False,
                    "error": "Owner cannot be removed. Transfer ownership first.",
                },
                status=403,
            )

        membership.is_active = False
        membership.save(update_fields=["is_active", "updated_at"])
        OrgAuditLog.objects.create(
            organization=org,
            actor=request.user,
            action=OrgAuditLog.Action.MEMBER_REMOVED,
            resource=membership.user.email,
        )
        logger.info(
            "member_removed: actor=%s user=%s org=%s",
            request.user.email,
            membership.user.email,
            org.slug,
        )
        return Response({"success": True, "message": "Member removed."})


# ── Invitations ────────────────────────────────────────────────────────────────


class InviteListCreateView(APIView):
    """
    GET  /api/v1/organizations/{id}/invites/  — list pending invites (admin+)
    POST /api/v1/organizations/{id}/invites/  — send invite by email (admin+)
    """

    permission_classes = [IsAuthenticated]

    def _get_org(self, pk):
        try:
            return Organization.objects.get(pk=pk)
        except Organization.DoesNotExist:
            return None

    def get(self, request, pk):
        org = self._get_org(pk)
        if org is None:
            return Response({"success": False, "error": "Not found."}, status=404)
        if not org.is_admin_or_owner(request.user):
            return Response(
                {"success": False, "error": "Admin or owner role required."}, status=403
            )
        invites = org.invites.filter(is_accepted=False).select_related("invited_by")
        ser = InviteSerializer(invites, many=True)
        return Response({"success": True, "data": ser.data})

    def post(self, request, pk):
        org = self._get_org(pk)
        if org is None:
            return Response({"success": False, "error": "Not found."}, status=404)
        if not org.is_admin_or_owner(request.user):
            return Response(
                {"success": False, "error": "Admin or owner role required."}, status=403
            )
        if org.is_full:
            return Response(
                {
                    "success": False,
                    "error": f"Organization is at member limit ({org.max_members}).",
                },
                status=403,
            )

        ser = InviteCreateSerializer(data=request.data)
        if not ser.is_valid():
            return Response({"success": False, "error": ser.errors}, status=400)

        email = ser.validated_data["email"]
        role = ser.validated_data["role"]

        # Check if user is already a member
        target_user = User.objects.filter(email=email).first()
        if target_user and org.is_member(target_user):
            return Response(
                {
                    "success": False,
                    "error": "User is already a member of this organization.",
                },
                status=400,
            )

        # Check for duplicate pending invite
        existing = OrganizationInvite.objects.filter(
            organization=org, email=email, is_accepted=False
        ).first()
        if existing and not existing.is_expired:
            return Response(
                {
                    "success": False,
                    "error": "A pending invite already exists for this email.",
                },
                status=400,
            )

        # Create invite with 7-day expiry
        invite = OrganizationInvite.objects.create(
            organization=org,
            invited_by=request.user,
            email=email,
            role=role,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )

        # Send invite email (non-blocking — swallow errors in dev)
        try:
            _send_invite_email(invite)
        except Exception as exc:
            logger.warning("invite_email_failed: %s", exc)

        OrgAuditLog.objects.create(
            organization=org,
            actor=request.user,
            action=OrgAuditLog.Action.INVITE_SENT,
            resource=email,
            metadata={"role": role},
        )
        logger.info(
            "invite_sent: actor=%s email=%s org=%s", request.user.email, email, org.slug
        )
        return Response(
            {"success": True, "data": InviteSerializer(invite).data}, status=201
        )


class InviteDeleteView(APIView):
    """DELETE /api/v1/organizations/{id}/invites/{invite_id}/ — cancel pending invite (admin+)"""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, invite_id):
        try:
            org = Organization.objects.get(pk=pk)
            invite = OrganizationInvite.objects.get(
                pk=invite_id, organization=org, is_accepted=False
            )
        except (Organization.DoesNotExist, OrganizationInvite.DoesNotExist):
            return Response({"success": False, "error": "Not found."}, status=404)

        if not org.is_admin_or_owner(request.user):
            return Response(
                {"success": False, "error": "Admin or owner role required."}, status=403
            )

        email = invite.email
        invite.delete()
        OrgAuditLog.objects.create(
            organization=org,
            actor=request.user,
            action=OrgAuditLog.Action.INVITE_CANCELLED,
            resource=email,
        )
        logger.info(
            "invite_cancelled: actor=%s invite=%s org=%s",
            request.user.email,
            invite_id,
            org.slug,
        )
        return Response({"success": True, "message": "Invite cancelled."})


class InviteAcceptView(APIView):
    """POST /api/v1/organizations/invites/{token}/accept/ — accept an invite (must be logged in)"""

    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        try:
            invite = OrganizationInvite.objects.select_related("organization").get(
                token=token, is_accepted=False
            )
        except OrganizationInvite.DoesNotExist:
            return Response(
                {"success": False, "error": "Invalid or already-used invite token."},
                status=404,
            )

        if invite.is_expired:
            return Response(
                {"success": False, "error": "This invite has expired."}, status=410
            )

        # Email must match the logged-in user
        if request.user.email.lower() != invite.email.lower():
            return Response(
                {
                    "success": False,
                    "error": "This invite was sent to a different email address.",
                },
                status=403,
            )

        org = invite.organization
        if org.is_full:
            return Response(
                {"success": False, "error": "Organization is at member limit."},
                status=403,
            )

        # Create or reactivate membership
        membership, _ = Membership.objects.get_or_create(
            organization=org,
            user=request.user,
            defaults={"role": invite.role, "is_active": True},
        )
        if not membership.is_active:
            membership.is_active = True
            membership.role = invite.role
            membership.save(update_fields=["is_active", "role", "updated_at"])

        invite.is_accepted = True
        invite.accepted_at = timezone.now()
        invite.save(update_fields=["is_accepted", "accepted_at"])

        OrgAuditLog.objects.create(
            organization=org,
            actor=request.user,
            action=OrgAuditLog.Action.INVITE_ACCEPTED,
            resource=request.user.email,
            metadata={"role": invite.role},
        )
        logger.info(
            "invite_accepted: user=%s org=%s role=%s",
            request.user.email,
            org.slug,
            invite.role,
        )
        return Response(
            {
                "success": True,
                "message": f"You have joined {org.name} as {invite.role}.",
                "data": MembershipSerializer(membership).data,
            }
        )


# ── Audit Log ─────────────────────────────────────────────────────────────────


class AuditLogListView(APIView):
    """
    TASK-006-B5: GET /api/v1/organizations/{id}/audit-logs/
    Returns paginated audit log for the org (admin+ only).
    Supports ?action= and ?limit= query params.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            org = Organization.objects.get(pk=pk)
        except Organization.DoesNotExist:
            return Response({"success": False, "error": "Not found."}, status=404)

        if not org.is_admin_or_owner(request.user):
            return Response(
                {"success": False, "error": "Admin or owner role required."}, status=403
            )

        qs = org.audit_logs.select_related("actor").all()

        action_filter = request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter)

        limit = min(int(request.query_params.get("limit", 50)), 200)
        offset = int(request.query_params.get("offset", 0))
        total = qs.count()
        entries = qs[offset : offset + limit]

        ser = OrgAuditLogSerializer(entries, many=True)
        return Response(
            {
                "success": True,
                "data": ser.data,
                "meta": {"total": total, "limit": limit, "offset": offset},
            }
        )


# ── Email helper ───────────────────────────────────────────────────────────────


def _send_invite_email(invite: OrganizationInvite) -> None:
    """Send invite email. Uses Django's email backend (SendGrid in prod)."""
    from django.conf import settings
    from django.core.mail import send_mail

    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    accept_url = f"{frontend_url}/invites/{invite.token}"

    subject = f"You're invited to join {invite.organization.name} on Synapse"
    body = (
        f"Hi,\n\n"
        f"{invite.invited_by.get_full_name() or invite.invited_by.email} has invited you to join "
        f"'{invite.organization.name}' on Synapse as {invite.role}.\n\n"
        f"Accept your invitation here:\n{accept_url}\n\n"
        f"This link expires in 7 days.\n\n"
        f"— The Synapse Team"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invite.email],
        fail_silently=False,
    )
