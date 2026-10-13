from django.conf import settings
from django.db import models

from applications.candidatures.models import Inscription
from applications.entites.models import Entite


class JournalAction(models.Model):
    class Action(models.TextChoices):
        VALIDATION = "VALIDATION", "Validation"
        REJET = "REJET", "Rejet"
        MODIFICATION_STATUT = "MODIFICATION_STATUT", "Modification du statut"
        SUPPRESSION = "SUPPRESSION", "Suppression"
        AFFECTATION_SALLE = "AFFECTATION_SALLE", "Affectation de salle"
        CREATION_SALLE = "CREATION_SALLE", "Création d’une salle"
        MODIFICATION_SALLE = "MODIFICATION_SALLE", "Modification d’une salle"
        SUPPRESSION_SALLE = "SUPPRESSION_SALLE", "Suppression d’une salle"
        CREATION_OPTION = "CREATION_OPTION", "Création d’une option"
        MODIFICATION_OPTION = "MODIFICATION_OPTION", "Modification d’une option"
        SUPPRESSION_OPTION = "SUPPRESSION_OPTION", "Suppression d’une option"
        CREATION_HORAIRE = "CREATION_HORAIRE", "Création d’un horaire"
        MODIFICATION_HORAIRE = "MODIFICATION_HORAIRE", "Modification d’un horaire"
        SUPPRESSION_HORAIRE = "SUPPRESSION_HORAIRE", "Suppression d’un horaire"
        CREATION_RESULTAT = "CREATION_RESULTAT", "Création d’un résultat"
        MODIF_RESULTAT = "MODIF_RESULTAT", "Modification d’un résultat"
        MODIFICATION_DOSSIER = "MODIFICATION_DOSSIER", "Modification d’un dossier"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="actions_administration",
        verbose_name="utilisateur",
    )
    inscription = models.ForeignKey(
        Inscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions_journalisees",
        verbose_name="inscription",
    )
    entite = models.ForeignKey(
        Entite,
        on_delete=models.SET_NULL,
        null=True,
        related_name="actions_journalisees",
        verbose_name="entité",
    )
    action = models.CharField("action", max_length=20, choices=Action.choices)
    date_action = models.DateTimeField("date de l’action", auto_now_add=True)
    details = models.JSONField("détails", default=dict, blank=True)

    class Meta:
        ordering = ["-date_action"]
        verbose_name = "action journalisée"
        verbose_name_plural = "journal des actions"

    def __str__(self):
        return f"{self.get_action_display()} - {self.date_action:%Y-%m-%d %H:%M}"
