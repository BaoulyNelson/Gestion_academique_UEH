from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator

from applications.candidatures.models import Inscription


class Resultat(models.Model):
    inscription = models.OneToOneField(
        Inscription,
        on_delete=models.CASCADE,
        related_name="resultat",
        verbose_name="inscription",
    )
    admis = models.BooleanField("admis", default=False)
    note = models.DecimalField(
        "note", max_digits=5, decimal_places=2, null=True, blank=True
    )
    publie = models.BooleanField("publié", default=False)
    date_publication = models.DateTimeField(
        "date de publication", null=True, blank=True
    )

    class Meta:
        verbose_name = "résultat"
        verbose_name_plural = "résultats"

    def __str__(self):
        return f"Résultat {self.inscription.numero_dossier}"

    @property
    def total_pondere(self):
        return sum(
            (epreuve.note * epreuve.coefficient for epreuve in self.epreuves.all()),
            Decimal("0.00"),
        )

    @property
    def bareme_pondere(self):
        return sum(
            (epreuve.bareme * epreuve.coefficient for epreuve in self.epreuves.all()),
            Decimal("0.00"),
        )

    @property
    def moyenne_calculee(self):
        bareme = self.bareme_pondere
        if not bareme:
            return self.note
        return (self.total_pondere / bareme * Decimal("100")).quantize(Decimal("0.01"))

    @property
    def admis_calcule(self):
        moyenne = self.moyenne_calculee
        return moyenne is not None and moyenne >= Decimal("65.00")


class EpreuveResultat(models.Model):
    resultat = models.ForeignKey(
        Resultat,
        on_delete=models.CASCADE,
        related_name="epreuves",
        verbose_name="résultat",
    )
    nom = models.CharField("épreuve", max_length=120)
    note = models.DecimalField("note obtenue", max_digits=7, decimal_places=2)
    bareme = models.DecimalField("barème", max_digits=7, decimal_places=2)
    coefficient = models.DecimalField(
        "coefficient",
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    ordre = models.PositiveSmallIntegerField("ordre d’affichage", default=0)

    class Meta:
        ordering = ["ordre", "pk"]
        verbose_name = "épreuve de résultat"
        verbose_name_plural = "épreuves de résultat"

    def __str__(self):
        return self.nom

    @property
    def note_ponderee(self):
        return self.note * self.coefficient

    @property
    def bareme_pondere(self):
        return self.bareme * self.coefficient
