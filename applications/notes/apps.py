from django.apps import AppConfig


class NotesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.notes"
    label = "notes"
    verbose_name = "Notes et evaluations"
