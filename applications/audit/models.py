from django.conf import settings
from django.db import models


class JournalAction(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions_journalisees",
    )
    action = models.CharField("action", max_length=80)
    type_objet = models.CharField("type d'objet", max_length=100)
    identifiant_objet = models.CharField(
        "identifiant de l'objet", max_length=64, blank=True
    )
    details = models.JSONField("details", default=dict, blank=True)
    adresse_ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    date_creation = models.DateTimeField("date", auto_now_add=True)

    class Meta:
        ordering = ("-date_creation",)
        verbose_name = "action journalisee"
        verbose_name_plural = "journal des actions"

    def __str__(self):
        return f"{self.action} - {self.date_creation:%Y-%m-%d %H:%M}"
