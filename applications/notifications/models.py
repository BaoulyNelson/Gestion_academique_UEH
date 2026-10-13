from django.conf import settings
from django.db import models


class Notification(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="utilisateur",
    )
    titre = models.CharField("titre", max_length=180)
    message = models.TextField("message")
    lue = models.BooleanField("lue", default=False)
    date_creation = models.DateTimeField("date de création", auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]
        verbose_name = "notification"
        verbose_name_plural = "notifications"

    def __str__(self):
        return self.titre
