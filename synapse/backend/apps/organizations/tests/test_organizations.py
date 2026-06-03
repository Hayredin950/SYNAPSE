"""
TASK-006-T1 / TASK-006-T2 / TASK-006-T3
Unit + integration tests for Team Workspaces & Organizations.

Covers:
  - Model helpers (is_member, is_admin_or_owner, user_role, is_full)
  - RBAC: owner/admin/member/viewer roles
  - Org CRUD endpoints
  - Member management endpoints
  - Invite flow: create → accept → membership created
  - Permission guard: member can't delete org; viewer can't manage members
"""

from __future__ import annotations

from apps.organizations.models import (
    Membership,
    Organization,
    OrganizationInvite,
    OrgRole,
)

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_user(email, password="pass1234!"):
    username = email.split("@")[0] + "_" + email.split("@")[1].replace(".", "_")
    return User.objects.create_user(username=username, email=email, password=password)


def _make_org(owner, name="Acme Corp"):
    org = Organization.objects.create(name=name, owner=owner)
    Membership.objects.create(
        organization=org, user=owner, role=OrgRole.OWNER, is_active=True
    )
    return org


# ── Model unit tests ──────────────────────────────────────────────────────────


class OrganizationModelTests(TestCase):

    def setUp(self):
        self.owner = _make_user("owner@acme.com")
        self.member_user = _make_user("member@acme.com")
        self.org = _make_org(self.owner)

    def test_slug_auto_generated(self):
        self.assertTrue(self.org.slug)
        self.assertIn("acme", self.org.slug)

    def test_slug_unique_on_collision(self):
        org2 = Organization.objects.create(name="Acme Corp", owner=self.owner)
        self.assertNotEqual(self.org.slug, org2.slug)

    def test_is_member_true_for_active_membership(self):
        Membership.objects.create(
            organization=self.org,
            user=self.member_user,
            role=OrgRole.MEMBER,
            is_active=True,
        )
        self.assertTrue(self.org.is_member(self.member_user))

    def test_is_member_false_for_inactive_membership(self):
        Membership.objects.create(
            organization=self.org,
            user=self.member_user,
            role=OrgRole.MEMBER,
            is_active=False,
        )
        self.assertFalse(self.org.is_member(self.member_user))

    def test_is_member_false_for_non_member(self):
        stranger = _make_user("stranger@acme.com")
        self.assertFalse(self.org.is_member(stranger))

    def test_user_role_owner(self):
        self.assertEqual(self.org.user_role(self.owner), OrgRole.OWNER)

    def test_user_role_none_for_non_member(self):
        stranger = _make_user("stranger2@acme.com")
        self.assertIsNone(self.org.user_role(stranger))

    def test_is_admin_or_owner_true_for_owner(self):
        self.assertTrue(self.org.is_admin_or_owner(self.owner))

    def test_is_admin_or_owner_true_for_admin(self):
        Membership.objects.create(
            organization=self.org,
            user=self.member_user,
            role=OrgRole.ADMIN,
            is_active=True,
        )
        self.assertTrue(self.org.is_admin_or_owner(self.member_user))

    def test_is_admin_or_owner_false_for_member(self):
        Membership.objects.create(
            organization=self.org,
            user=self.member_user,
            role=OrgRole.MEMBER,
            is_active=True,
        )
        self.assertFalse(self.org.is_admin_or_owner(self.member_user))

    def test_member_count(self):
        self.assertEqual(self.org.member_count, 1)  # just owner
        Membership.objects.create(
            organization=self.org,
            user=self.member_user,
            role=OrgRole.MEMBER,
            is_active=True,
        )
        self.assertEqual(self.org.member_count, 2)

    def test_is_full_free_plan(self):
        # Free plan: max 5 members
        for i in range(4):  # owner + 4 more = 5
            u = _make_user(f"extra{i}@acme.com")
            Membership.objects.create(
                organization=self.org, user=u, role=OrgRole.MEMBER, is_active=True
            )
        self.assertTrue(self.org.is_full)

    def test_str(self):
        self.assertIn("Acme Corp", str(self.org))

    def test_invite_is_expired_false_when_no_expiry(self):
        invite = OrganizationInvite.objects.create(
            organization=self.org,
            invited_by=self.owner,
            email="x@x.com",
            role=OrgRole.MEMBER,
        )
        self.assertFalse(invite.is_expired)


# ── API endpoint tests ────────────────────────────────────────────────────────


class OrgListCreateAPITests(TestCase):

    def setUp(self):
        self.owner = _make_user("owner2@acme.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)
        self.url = reverse("org-list-create")

    def test_unauthenticated_returns_401(self):
        c = APIClient()
        resp = c.get(self.url)
        self.assertEqual(resp.status_code, 401)

    def test_create_org(self):
        resp = self.client.post(self.url, {"name": "Test Org"}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["data"]["name"], "Test Org")

    def test_create_org_auto_assigns_owner_membership(self):
        self.client.post(self.url, {"name": "Auto Org"}, format="json")
        org = Organization.objects.get(name="Auto Org")
        self.assertTrue(
            Membership.objects.filter(
                organization=org, user=self.owner, role=OrgRole.OWNER
            ).exists()
        )

    def test_list_orgs_returns_user_orgs(self):
        _make_org(self.owner, "My Org")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data["data"]), 1)

    def test_create_org_name_too_short(self):
        resp = self.client.post(self.url, {"name": "A"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_create_org_exceeds_free_limit(self):
        # Owner already has 1 org; free limit is 1
        _make_org(self.owner, "Org Already Exists")
        resp = self.client.post(self.url, {"name": "Second Org"}, format="json")
        self.assertEqual(resp.status_code, 403)


class OrgDetailAPITests(TestCase):

    def setUp(self):
        self.owner = _make_user("owner3@acme.com")
        self.member_user = _make_user("member3@acme.com")
        self.stranger = _make_user("stranger3@acme.com")
        self.org = _make_org(self.owner)
        Membership.objects.create(
            organization=self.org,
            user=self.member_user,
            role=OrgRole.MEMBER,
            is_active=True,
        )
        self.url = reverse("org-detail", kwargs={"pk": self.org.pk})

    def _auth(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_owner_can_get_detail(self):
        resp = self._auth(self.owner).get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["name"], self.org.name)

    def test_member_can_get_detail(self):
        resp = self._auth(self.member_user).get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_non_member_cannot_get_detail(self):
        resp = self._auth(self.stranger).get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_owner_can_patch(self):
        resp = self._auth(self.owner).patch(
            self.url, {"name": "Updated Name"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, "Updated Name")

    def test_member_cannot_patch(self):
        resp = self._auth(self.member_user).patch(
            self.url, {"name": "Hacked"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_owner_can_delete(self):
        resp = self._auth(self.owner).delete(self.url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Organization.objects.filter(pk=self.org.pk).exists())

    def test_member_cannot_delete_org(self):
        """TASK-006-T3: member can't delete org."""
        resp = self._auth(self.member_user).delete(self.url)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Organization.objects.filter(pk=self.org.pk).exists())


class MemberAPITests(TestCase):

    def setUp(self):
        self.owner = _make_user("owner4@acme.com")
        self.admin = _make_user("admin4@acme.com")
        self.member_user = _make_user("member4@acme.com")
        self.new_user = _make_user("newuser4@acme.com")
        self.org = _make_org(self.owner)
        Membership.objects.create(
            organization=self.org, user=self.admin, role=OrgRole.ADMIN, is_active=True
        )
        Membership.objects.create(
            organization=self.org,
            user=self.member_user,
            role=OrgRole.MEMBER,
            is_active=True,
        )
        self.list_url = reverse("org-member-list", kwargs={"pk": self.org.pk})

    def _auth(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_list_members(self):
        resp = self._auth(self.owner).get(self.list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["data"]), 3)  # owner + admin + member

    def test_add_member_as_admin(self):
        resp = self._auth(self.admin).post(
            self.list_url,
            {"user_id": str(self.new_user.pk), "role": "member"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(self.org.is_member(self.new_user))

    def test_member_cannot_add_member(self):
        """TASK-006-T3: viewer/member can't manage membership."""
        resp = self._auth(self.member_user).post(
            self.list_url,
            {"user_id": str(self.new_user.pk), "role": "member"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_remove_self(self):
        url = reverse(
            "org-member-detail",
            kwargs={"pk": self.org.pk, "user_id": self.member_user.pk},
        )
        resp = self._auth(self.member_user).delete(url)
        self.assertEqual(resp.status_code, 200)
        self.org.memberships.get(user=self.member_user).refresh_from_db()
        self.assertFalse(self.org.memberships.get(user=self.member_user).is_active)

    def test_owner_cannot_be_removed(self):
        url = reverse(
            "org-member-detail", kwargs={"pk": self.org.pk, "user_id": self.owner.pk}
        )
        resp = self._auth(self.admin).delete(url)
        self.assertEqual(resp.status_code, 403)

    def test_change_member_role(self):
        url = reverse(
            "org-member-detail",
            kwargs={"pk": self.org.pk, "user_id": self.member_user.pk},
        )
        resp = self._auth(self.owner).patch(url, {"role": "admin"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.org.memberships.get(user=self.member_user).refresh_from_db()
        self.assertEqual(
            self.org.memberships.get(user=self.member_user).role, OrgRole.ADMIN
        )


class InviteAPITests(TestCase):

    def setUp(self):
        self.owner = _make_user("owner5@acme.com")
        self.member_user = _make_user("member5@acme.com")
        self.invitee = _make_user("invitee5@acme.com")
        self.org = _make_org(self.owner)
        Membership.objects.create(
            organization=self.org,
            user=self.member_user,
            role=OrgRole.MEMBER,
            is_active=True,
        )
        self.invite_url = reverse("org-invite-list", kwargs={"pk": self.org.pk})

    def _auth(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_owner_can_create_invite(self):
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            resp = self._auth(self.owner).post(
                self.invite_url,
                {"email": "invitee5@acme.com", "role": "member"},
                format="json",
            )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            OrganizationInvite.objects.filter(
                email="invitee5@acme.com", organization=self.org
            ).exists()
        )

    def test_member_cannot_create_invite(self):
        resp = self._auth(self.member_user).post(
            self.invite_url, {"email": "anyone@x.com", "role": "member"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_accept_invite(self):
        """TASK-006-T4: create invite → accept → membership created."""
        from django.utils import timezone

        invite = OrganizationInvite.objects.create(
            organization=self.org,
            invited_by=self.owner,
            email="invitee5@acme.com",
            role=OrgRole.MEMBER,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        accept_url = reverse("org-invite-accept", kwargs={"token": invite.token})
        resp = self._auth(self.invitee).post(accept_url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.org.is_member(self.invitee))
        invite.refresh_from_db()
        self.assertTrue(invite.is_accepted)

    def test_accept_invite_wrong_user_email(self):
        from django.utils import timezone

        wrong_user = _make_user("wrong5@acme.com")
        invite = OrganizationInvite.objects.create(
            organization=self.org,
            invited_by=self.owner,
            email="invitee5@acme.com",
            role=OrgRole.MEMBER,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        accept_url = reverse("org-invite-accept", kwargs={"token": invite.token})
        resp = self._auth(wrong_user).post(accept_url)
        self.assertEqual(resp.status_code, 403)

    def test_cancel_invite(self):
        from django.utils import timezone

        invite = OrganizationInvite.objects.create(
            organization=self.org,
            invited_by=self.owner,
            email="cancel5@acme.com",
            role=OrgRole.MEMBER,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        del_url = reverse(
            "org-invite-delete", kwargs={"pk": self.org.pk, "invite_id": invite.pk}
        )
        resp = self._auth(self.owner).delete(del_url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(OrganizationInvite.objects.filter(pk=invite.pk).exists())
