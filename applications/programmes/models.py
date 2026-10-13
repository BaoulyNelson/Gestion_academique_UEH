from django.db import models

from applications.entites.models import Entite


class Programme(models.Model):
    entite = models.ForeignKey(
        Entite,
        on_delete=models.CASCADE,
        related_name="programmes",
        verbose_name="entité",
    )
    nom = models.CharField("nom", max_length=200)
    description = models.TextField("description", blank=True)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        ordering = ["nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["entite", "nom"], name="programme_nom_unique_par_entite"
            )
        ]
        verbose_name = "programme"
        verbose_name_plural = "programmes"

    def __str__(self):
        return self.nom
