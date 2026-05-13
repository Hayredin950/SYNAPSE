"""
Celery tasks for user management.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def send_welcome_email_task(self, user_id: str):
    """
    Celery task to send welcome email after onboarding.
    Runs asynchronously so it doesn't block the endpoint.
    """
    try:
        from apps.users.models import User
        from apps.users.onboarding_views import _send_welcome_email

        user = User.objects.get(id=user_id)
        _send_welcome_email(user)
        logger.info(f"Sent welcome email to {user.email}")

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for welcome email")
    except Exception as exc:
        logger.warning(f"Failed to send welcome email to user {user_id}: {exc}")
        # Don't retry email failures - not critical
        pass


@shared_task(bind=True, max_retries=3, name='apps.users.tasks.create_initial_workflows_task')
def create_initial_workflows_task(self, user_id: str, prefs_id: str):
    """
    Celery task to create initial workflows for a new user.
    Runs asynchronously in the background so it doesn't block the onboarding endpoint.
    """
    logger.info(f"[ONBOARDING] Starting create_initial_workflows_task for user {user_id}")
    try:
        from apps.users.models import User, OnboardingPreferences

        user = User.objects.get(id=user_id)
        logger.info(f"[ONBOARDING] Found user: {user.email}")
        
        prefs = OnboardingPreferences.objects.get(id=prefs_id)
        logger.info(f"[ONBOARDING] Found prefs with interests: {prefs.interests}")

        # Import here to avoid circular imports
        from apps.users.onboarding_views import _create_initial_workflows

        _create_initial_workflows(user, prefs)
        logger.info(f"[ONBOARDING] Successfully created initial workflows for user {user.email}")
        return {"success": True, "user_id": user_id}

    except User.DoesNotExist:
        logger.error(f"[ONBOARDING] User {user_id} not found for onboarding")
        return {"success": False, "error": "User not found"}
    except OnboardingPreferences.DoesNotExist:
        logger.error(f"[ONBOARDING] OnboardingPreferences {prefs_id} not found for onboarding")
        return {"success": False, "error": "Preferences not found"}
    except Exception as exc:
        logger.exception(f"[ONBOARDING] Failed to create initial workflows for user {user_id}: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60)
