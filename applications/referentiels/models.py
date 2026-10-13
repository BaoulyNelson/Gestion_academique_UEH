from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Entite(models.Model):
    class Regime(models.TextChoices):
        COHORTE = "cohorte", "Cohorte"
        CREDITS = "credits", "Credits"

    code = models.SlugField("code", max_length=24, unique=True)
    nom = models.CharField("nom", max_length=160)
    regime = models.CharField(
        "regime academique", max_length=12, choices=Regime.choices
    )
    est_active = models.BooleanField("active", default=True)

    class Meta:
        ordering = ("nom",)
        verbose_name = "entite"
        verbose_name_plural = "entites"

    def __str__(self):
        return self.nom


class Programme(models.Model):
    class TypeProgramme(models.TextChoices):
        PROPEDEUTIQUE = "propedeutique", "Propedeutique"
        SPECIALITE = "specialite", "Specialite"
        FORMATION = "formation", "Autre formation"

    entite = models.ForeignKey(
        Entite,
        verbose_name="entite",
        on_delete=models.PROTECT,
        related_name="programmes",
    )
    code = models.SlugField("code", max_length=32)
    nom = models.CharField("nom", max_length=180)
    type_programme = models.CharField(
        "type", max_length=20, choices=TypeProgramme.choices
    )
    duree_annees = models.DecimalField(
        "duree en annees", max_digits=4, decimal_places=1, null=True, blank=True
    )
    credits_requis = models.PositiveSmallIntegerField(
        "credits requis", null=True, blank=True
    )
    est_actif = models.BooleanField("actif", default=True)

    class Meta:
        ordering = ("entite__nom", "nom")
        constraints = [
            models.UniqueConstraint(
                fields=("entite", "code"), name="uniq_programme_entite_code"
            )
        ]
        verbose_name = "programme"
        verbose_name_plural = "programmes"

    def __str__(self):
        return f"{self.entite.code} - {self.nom}"


class Cours(models.Model):
    programme = models.ForeignKey(
        Programme,
        verbose_name="programme",
        on_delete=models.PROTECT,
        related_name="cours",
    )
    code = models.CharField("code", max_length=32)
    nom = models.CharField("nom", max_length=180)
    credits = models.DecimalField(
        "credits",
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    est_obligatoire = models.BooleanField("cours obligatoire", default=True)
    est_actif = models.BooleanField("actif", default=True)

    class Meta:
        ordering = ("programme__nom", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("programme", "code"), name="uniq_cours_programme_code"
            )
        ]
        verbose_name = "cours"
        verbose_name_plural = "cours"

    def __str__(self):
        return f"{self.code} - {self.nom}"


class PeriodeAcademique(models.Model):
    class TypePeriode(models.TextChoices):
        ANNEE = "annee", "Annee"
        SESSION = "session", "Session"
        TRIMESTRE = "trimestre", "Trimestre"
        SEMESTRE = "semestre", "Semestre"
        QUADRIMESTRE = "quadrimestre", "Quadrimestre"
        NIVEAU = "niveau", "Niveau"

    entite = models.ForeignKey(
        Entite, verbose_name="entite", on_delete=models.PROTECT, related_name="periodes"
    )
    code = models.CharField("code", max_length=32)
    nom = models.CharField("nom", max_length=100)
    annee_academique = models.CharField("annee academique", max_length=20)
    type_periode = models.CharField(
        "type de periode", max_length=16, choices=TypePeriode.choices
    )
    date_debut = models.DateField("date de debut", null=True, blank=True)
    date_fin = models.DateField("date de fin", null=True, blank=True)
    est_ouverte = models.BooleanField("ouverte aux inscriptions", default=False)

    class Meta:
        ordering = ("-annee_academique", "date_debut", "nom")
        constraints = [
            models.UniqueConstraint(
                fields=("entite", "code"), name="uniq_periode_entite_code"
            )
        ]
        verbose_name = "periode academique"
        verbose_name_plural = "periodes academiques"

    def __str__(self):
        return f"{self.nom} ({self.annee_academique})"


class RegleAcademique(models.Model):
    entite = models.ForeignKey(
        Entite, verbose_name="entite", on_delete=models.PROTECT, related_name="regles"
    )
    version = models.CharField("version du reglement", max_length=40)
    date_effet = models.DateField("date d'effet")
    parametres = models.JSONField("parametres academiques", default=dict)
    est_active = models.BooleanField("active", default=True)

    class Meta:
        ordering = ("entite__nom", "-date_effet")
        verbose_name = "regle academique"
        verbose_name_plural = "regles academiques"

    def __str__(self):
        return f"{self.entite} - {self.version}"


class AffectationCours(models.Model):
    professeur = models.ForeignKey(
        "comptes.Utilisateur",
        verbose_name="professeur",
        on_delete=models.PROTECT,
        related_name="affectations_cours",
    )
    cours = models.ForeignKey(
        Cours,
        verbose_name="cours",
        on_delete=models.PROTECT,
        related_name="affectations_professeurs",
    )
    periode = models.ForeignKey(
        PeriodeAcademique,
        verbose_name="periode academique",
        on_delete=models.PROTECT,
        related_name="affectations_cours",
    )

    class Meta:
        ordering = ("periode", "cours__code", "professeur__last_name")
        constraints = [
            models.UniqueConstraint(
                fields=("professeur", "cours", "periode"),
                name="uniq_affectation_prof_cours_periode",
            )
        ]
        verbose_name = "affectation de cours"
        verbose_name_plural = "affectations de cours"

    def clean(self):
        erreurs = {}
        if (
            self.professeur_id
            and self.professeur.role != self.professeur.Role.PROFESSEUR
        ):
            erreurs["professeur"] = "Le compte doit avoir le role professeur."
        if self.cours_id and self.periode_id:
            if self.cours.programme.entite_id != self.periode.entite_id:
                erreurs["periode"] = (
                    "Le cours et la periode doivent appartenir a la meme entite."
                )
        if erreurs:
            raise ValidationError(erreurs)

    def __str__(self):
        return f"{self.professeur} - {self.cours} - {self.periode}"
