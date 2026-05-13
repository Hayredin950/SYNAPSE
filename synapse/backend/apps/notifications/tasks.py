"""
Celery tasks for the Notifications app.

Phase 4.2 — SendGrid email delivery tasks.
Phase 2 (TASK-201) — Weekly AI digest email.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def push_notification_to_ws(notification) -> None:
    """Push a notification to the user's WebSocket channel (non-blocking)."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        group_name = f"notifications_{notification.user_id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "notify",
                "data": {
                    "id": str(notification.id),
                    "title": notification.title,
                    "message": notification.message,
                    "notif_type": notification.notif_type,
                    "is_read": False,
                    "created_at": notification.created_at.isoformat(),
                    "metadata": notification.metadata or {},
                },
            },
        )
        logger.info(
            "WS push: user=%s title=%s", notification.user_id, notification.title
        )
    except Exception as exc:
        logger.warning("WS push failed (non-critical): %s", exc)


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    name="apps.notifications.tasks.send_notification_email_task",
)
def send_notification_email_task(
    self,
    notification_id: str,
) -> dict:
    """
    Send an email for a given Notification record.

    Looks up the Notification, builds the email content, and delivers
    it via the configured email backend (SendGrid SMTP or console).

    Args:
        notification_id: UUID string of the Notification to email.

    Returns:
        dict with status and notification_id.
    """
    from .email_service import send_notification_email
    from .models import Notification

    try:
        notification = Notification.objects.select_related("user").get(
            id=notification_id
        )
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found — cannot send email.")
        return {"status": "failed", "reason": "Notification not found"}

    user = notification.user
    success = send_notification_email(
        to_email=user.email,
        subject=notification.title,
        message=notification.message,
    )

    if success:
        logger.info(f"Email sent for notification {notification_id} to {user.email}")
        return {"status": "sent", "notification_id": notification_id}
    else:
        logger.warning(f"Email delivery failed for notification {notification_id}")
        return self.retry(
            exc=Exception("Email delivery failed"),
            countdown=60 * (self.request.retries + 1),
        )


@shared_task(
    bind=True,
    max_retries=3,
    name="apps.notifications.tasks.send_weekly_digest_task",
)
def send_weekly_digest_task(self, user_id: str) -> dict:
    """
    Send the weekly AI digest email to a single user.

    Fetches the top 5 trending articles, papers, and repositories from
    the past 7 days and delivers them via send_weekly_digest_email().

    Args:
        user_id: UUID string of the User to send the digest to.

    Returns:
        dict with status and user email.
    """
    from datetime import timedelta

    from apps.users.models import User

    from django.utils import timezone

    from .email_service import send_weekly_digest_email

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error("Weekly digest: user %s not found", user_id)
        return {"status": "failed", "reason": "User not found"}

    if not user.digest_enabled:
        logger.info("Weekly digest: user %s has digest disabled — skipping", user.email)
        return {"status": "skipped", "reason": "digest_disabled"}

    since = timezone.now() - timedelta(days=7)

    # Top trending articles from the past week
    try:
        from apps.articles.models import Article

        articles = list(
            Article.objects.filter(published_at__gte=since).order_by("-trending_score")[
                :5
            ]
        )
    except Exception as exc:
        logger.warning("Weekly digest: failed to fetch articles: %s", exc)
        articles = []

    # Top research papers from the past week
    try:
        from apps.papers.models import ResearchPaper

        since_date = since.date()
        papers = list(
            ResearchPaper.objects.filter(published_date__gte=since_date).order_by(
                "-published_date"
            )[:5]
        )
    except Exception as exc:
        logger.warning("Weekly digest: failed to fetch papers: %s", exc)
        papers = []

    # Top trending repositories from the past week
    try:
        from apps.repositories.models import Repository

        repos = list(
            Repository.objects.filter(scraped_at__gte=since).order_by("-stars")[:5]
        )
    except Exception as exc:
        logger.warning("Weekly digest: failed to fetch repos: %s", exc)
        repos = []

    success = send_weekly_digest_email(
        user=user,
        articles=articles,
        papers=papers,
        repos=repos,
    )

    if success:
        logger.info("Weekly digest sent to %s", user.email)
        return {"status": "sent", "user": user.email}

    return self.retry(
        exc=Exception("Weekly digest delivery failed"),
        countdown=60 * (self.request.retries + 1),
    )


@shared_task(
    name="apps.notifications.tasks.send_weekly_digest_to_all",
)
def send_weekly_digest_to_all() -> dict:
    """
    Fan-out task: enqueue send_weekly_digest_task for every user with
    digest_enabled=True whose digest_day matches today.

    Scheduled by Celery Beat to run daily at 08:00 UTC so each user
    receives their digest on their chosen day of the week.

    Returns:
        dict with enqueued count.
    """
    from apps.users.models import User

    from django.utils import timezone

    today = timezone.now().strftime("%A").lower()  # e.g. 'monday'
    users = User.objects.filter(digest_enabled=True, digest_day=today, is_active=True)
    count = 0
    for user in users.iterator():
        send_weekly_digest_task.delay(str(user.id))
        count += 1

    logger.info("Weekly digest fan-out: enqueued %d emails for %s", count, today)
    return {"status": "enqueued", "count": count, "day": today}


@shared_task(
    bind=True,
    max_retries=3,
    name="apps.notifications.tasks.send_workflow_completion_email_task",
)
def send_workflow_completion_email_task(
    self,
    user_id: str,
    workflow_name: str,
    run_status: str,
    run_id: str,
) -> dict:
    """
    Send a workflow completion email to a user.

    Decoupled from the workflow execution task so email delivery
    does not block or fail the workflow itself.

    Args:
        user_id:       UUID string of the User to notify.
        workflow_name: Name of the completed workflow.
        run_status:    'success' or 'failed'.
        run_id:        UUID string of the WorkflowRun.

    Returns:
        dict with status.
    """
    from apps.users.models import User

    from .email_service import send_workflow_completion_email

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found — cannot send workflow email.")
        return {"status": "failed", "reason": "User not found"}

    success = send_workflow_completion_email(
        user=user,
        workflow_name=workflow_name,
        run_status=run_status,
        run_id=run_id,
    )

    if success:
        logger.info(f"Workflow completion email sent to {user.email}")
        return {"status": "sent", "user": user.email}
    else:
        return self.retry(
            exc=Exception("Workflow email delivery failed"),
            countdown=60 * (self.request.retries + 1),
        )
