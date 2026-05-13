"""
backend.apps.billing.tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Celery tasks for async Stripe webhook processing.

Phase 9.3 — Growth & Iteration
"""

import structlog

from celery import shared_task

logger = structlog.get_logger(__name__)

WEBHOOK_HANDLERS = {
    "customer.subscription.created": "handle_subscription_created",
    "customer.subscription.updated": "handle_subscription_updated",
    "customer.subscription.deleted": "handle_subscription_deleted",
    "invoice.payment_succeeded": "handle_invoice_paid",
    "invoice.payment_failed": "handle_payment_failed",
}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_stripe_webhook(self, event_type: str, event_data: dict) -> None:
    """
    Process a Stripe webhook event asynchronously.
    Retries up to 3 times on failure (with 60s delay).
    """
    handler_name = WEBHOOK_HANDLERS.get(event_type)

    if not handler_name:
        logger.debug("stripe_webhook_unhandled", event_type=event_type)
        return

    try:
        from apps.billing import stripe_service

        handler = getattr(stripe_service, handler_name)
        handler(event_data)
        logger.info("stripe_webhook_processed", event_type=event_type)
    except Exception as exc:
        logger.error("stripe_webhook_failed", event_type=event_type, error=str(exc))
        raise self.retry(exc=exc)
