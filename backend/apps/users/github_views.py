"""
SYNAPSE GitHub OAuth Views
Handles GitHub OAuth 2.0 login, callback, and account disconnect.

Flow:
    1. GET  /api/v1/auth/github/          → redirect to GitHub auth page
    2. GET  /api/v1/auth/github/callback/ → exchange code for token, create/link user
    3. DELETE /api/v1/auth/github/disconnect/ → unlink GitHub from account
"""

import logging
import os
import urllib.parse

import requests
from rest_framework_simplejwt.tokens import RefreshToken

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import User

logger = logging.getLogger(__name__)

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get(
    "GITHUB_REDIRECT_URI",
    "http://localhost:8000/api/v1/auth/github/callback/",
)
FRONTEND_URL = getattr(settings, "FRONTEND_URL", "http://localhost:3000")


def _get_tokens_for_user(user: User) -> dict:
    """Generate JWT access + refresh tokens for a user."""
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def github_auth(request):
    """
    GET /api/v1/auth/github/
    Redirects the user to GitHub's OAuth authorization page.
    """
    if not GITHUB_CLIENT_ID:
        return Response(
            {"error": "GitHub OAuth is not configured. Set GITHUB_CLIENT_ID."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    params = urllib.parse.urlencode(
        {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_REDIRECT_URI,
            "scope": "user:email read:user",
            "state": "synapse_github_oauth",  # In production, use a CSRF token
        }
    )
    github_auth_url = f"https://github.com/login/oauth/authorize?{params}"

    from django.shortcuts import redirect

    return redirect(github_auth_url)


@api_view(["GET"])
@permission_classes([AllowAny])
def github_callback(request):
    """
    GET /api/v1/auth/github/callback/
    Exchanges GitHub OAuth code for an access token, fetches user profile,
    creates or links a SYNAPSE account, and returns JWT tokens.
    On success, redirects to frontend with tokens in query params.
    """
    code = request.GET.get("code")
    error = request.GET.get("error")

    if error:
        frontend_error_url = f"{FRONTEND_URL}/login?error=github_denied"
        from django.shortcuts import redirect

        return redirect(frontend_error_url)

    if not code:
        return Response(
            {"error": "Missing OAuth code parameter."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Exchange code for GitHub access token ──────────────────────────────
    try:
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        token_response.raise_for_status()
        token_data = token_response.json()
    except requests.RequestException as exc:
        logger.error("GitHub token exchange failed: %s", exc)
        from django.shortcuts import redirect

        return redirect(f"{FRONTEND_URL}/login?error=github_token_failed")

    github_access_token = token_data.get("access_token")
    if not github_access_token:
        logger.error("GitHub returned no access_token: %s", token_data)
        from django.shortcuts import redirect

        return redirect(f"{FRONTEND_URL}/login?error=github_no_token")

    # ── Fetch GitHub user profile ──────────────────────────────────────────
    try:
        profile_resp = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {github_access_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
        profile_resp.raise_for_status()
        gh_profile = profile_resp.json()
    except requests.RequestException as exc:
        logger.error("GitHub profile fetch failed: %s", exc)
        from django.shortcuts import redirect

        return redirect(f"{FRONTEND_URL}/login?error=github_profile_failed")

    # ── Fetch primary email if not public ─────────────────────────────────
    gh_email = gh_profile.get("email")
    if not gh_email:
        try:
            emails_resp = requests.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {github_access_token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=10,
            )
            emails_resp.raise_for_status()
            emails = emails_resp.json()
            primary = next(
                (e for e in emails if e.get("primary") and e.get("verified")), None
            )
            gh_email = primary["email"] if primary else None
        except requests.RequestException:
            pass

    if not gh_email:
        from django.shortcuts import redirect

        return redirect(f"{FRONTEND_URL}/login?error=github_no_email")

    gh_id = str(gh_profile.get("id", ""))
    gh_username = gh_profile.get("login", "")
    gh_name = gh_profile.get("name", "") or gh_username
    gh_avatar = gh_profile.get("avatar_url", "")

    # ── Find or create SYNAPSE user ───────────────────────────────────────
    user = None

    # 1. Try to find by github_id
    try:
        user = User.objects.get(github_id=gh_id)
    except User.DoesNotExist:
        pass

    # 2. Try to find by email
    if user is None:
        try:
            user = User.objects.get(email=gh_email)
            # Link GitHub to existing account
            user.github_id = gh_id
            user.github_username = gh_username
            if not user.avatar_url and gh_avatar:
                user.avatar_url = gh_avatar
            user.save(update_fields=["github_id", "github_username", "avatar_url"])
            logger.info("Linked GitHub to existing user %s", user.email)
        except User.DoesNotExist:
            pass

    # 3. Create new user
    if user is None:
        # Derive a safe username from GitHub login
        base_username = gh_username or gh_email.split("@")[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        name_parts = (gh_name or "").split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        user = User.objects.create_user(
            username=username,
            email=gh_email,
            first_name=first_name,
            last_name=last_name,
            avatar_url=gh_avatar,
            github_id=gh_id,
            github_username=gh_username,
            email_verified=True,  # GitHub emails are already verified
        )
        user.set_unusable_password()
        user.save()
        logger.info("Created new user via GitHub OAuth: %s", user.email)

    # ── Sync GitHub starred repos to knowledge base (TASK-202-1) ─────────
    _sync_github_starred_repos.delay(gh_username, github_access_token)

    # ── Return JWT tokens via frontend redirect ───────────────────────────
    tokens = _get_tokens_for_user(user)
    redirect_url = (
        f"{FRONTEND_URL}/auth/github/success"
        f"?access={tokens['access']}"
        f"&refresh={tokens['refresh']}"
        f"&is_onboarded={str(user.is_onboarded).lower()}"
    )
    from django.shortcuts import redirect as django_redirect

    return django_redirect(redirect_url)


from celery import shared_task


@shared_task(
    name="apps.users.github_views.sync_github_starred_repos",
    max_retries=2,
    ignore_result=True,
)
def _sync_github_starred_repos(gh_username: str, github_access_token: str) -> None:
    """
    TASK-202-1: Sync a GitHub user's starred repositories into the SYNAPSE
    knowledge base.

    Fetches up to 100 starred repos (1 paginated API call) and upserts each
    one as a Repository record, then queues embedding generation for any
    newly-created repos.

    Args:
        gh_username:         GitHub login name (used for logging only).
        github_access_token: Short-lived GitHub OAuth access token.
    """
    from apps.repositories.embedding_tasks import generate_repo_embedding
    from apps.repositories.models import Repository

    headers = {
        "Authorization": f"Bearer {github_access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    import requests as _requests_lib  # local alias so mock patching doesn't break exception catching

    starred_repos = []
    # Fetch up to 2 pages (100 repos per page = 200 starred at most)
    for page in range(1, 3):
        try:
            resp = requests.get(
                "https://api.github.com/user/starred",
                headers=headers,
                params={"per_page": 100, "page": page},
                timeout=15,
            )
            resp.raise_for_status()
            page_data = resp.json()
            starred_repos.extend(page_data)
            if len(page_data) < 100:
                break  # last page
        except _requests_lib.RequestException as exc:
            logger.warning(
                "GitHub starred repos fetch failed for %s (page %d): %s",
                gh_username,
                page,
                exc,
            )
            break

    if not starred_repos:
        logger.info("No starred repos found for GitHub user %s", gh_username)
        return

    created_count = 0
    updated_count = 0

    for repo_data in starred_repos:
        gh_repo_id = repo_data.get("id")
        if not gh_repo_id:
            continue

        defaults = {
            "name": repo_data.get("name", ""),
            "full_name": repo_data.get("full_name", ""),
            "description": repo_data.get("description", "") or "",
            "url": repo_data.get("html_url", ""),
            "clone_url": repo_data.get("clone_url", "") or "",
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
            "watchers": repo_data.get("watchers_count", 0),
            "open_issues": repo_data.get("open_issues_count", 0),
            "language": repo_data.get("language", "") or "",
            "topics": repo_data.get("topics", []),
            "owner": (repo_data.get("owner") or {}).get("login", ""),
        }

        try:
            repo, created = Repository.objects.update_or_create(
                github_id=gh_repo_id,
                defaults=defaults,
            )
            if created:
                created_count += 1
                # Queue embedding for newly discovered repos
                generate_repo_embedding.delay(str(repo.id))
            else:
                updated_count += 1
        except Exception as exc:
            logger.warning(
                "Failed to upsert repo %s: %s",
                repo_data.get("full_name", gh_repo_id),
                exc,
            )
            continue

    logger.info(
        "GitHub starred repos sync for %s: %d created, %d updated",
        gh_username,
        created_count,
        updated_count,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def github_disconnect(request):
    """
    DELETE /api/v1/auth/github/disconnect/
    Unlinks GitHub from the authenticated user's account.
    Requires the user to have a password set (otherwise they'd lose login access).
    """
    user = request.user
    if not user.has_usable_password():
        return Response(
            {
                "error": "Cannot disconnect GitHub — you have no password set. Set a password first."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not user.github_id:
        return Response(
            {"error": "GitHub is not connected to your account."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.github_id = None
    user.github_username = ""
    user.save(update_fields=["github_id", "github_username"])
    logger.info("User %s disconnected GitHub", user.email)
    return Response(
        {"message": "GitHub account disconnected successfully."},
        status=status.HTTP_200_OK,
    )
