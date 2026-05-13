from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.automation"
    verbose_name = "Automation"

    def ready(self):
        # Wire event-trigger signals (new article, trending spike, etc.)
        from .signals import connect_signals

        connect_signals()
