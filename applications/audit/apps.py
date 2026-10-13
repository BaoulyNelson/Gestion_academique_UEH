from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.audit"
    label = "audit"
    verbose_name = "Journal des actions"
