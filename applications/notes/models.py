from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Evaluation(models.Model):
    cours = models.ForeignKey(
        "referentiels.Cours",
        verbose_name="cours",
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    periode = models.ForeignKey(
        "referentiels.PeriodeAcademique",
        verbose_name="periode academique",
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    etudiant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="etudiant",
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    libelle = models.CharField("libelle de l'evaluation", max_length=120)
    note = models.DecimalField(
        "note sur 100",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    coefficient = models.DecimalField(
        "coefficient",
        max_digits=5,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    est_publiee = models.BooleanField("publiee", default=False)
    saisie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="saisie par",
        on_delete=models.PROTECT,
        related_name="evaluations_saisies",
    )
    date_creation = models.DateTimeField("date de saisie", auto_now_add=True)
    date_modification = models.DateTimeField("date de modification", auto_now=True)

    class Meta:
        ordering = ("periode", "cours", "etudiant", "libelle")
        constraints = [
            models.UniqueConstraint(
                fields=("etudiant", "cours", "periode", "libelle"),
                name="uniq_evaluation_etudiant_cours_periode_libelle",
            )
        ]
        verbose_name = "evaluation"
        verbose_name_plural = "evaluations"

    def clean(self):
        erreurs = {}
        if self.etudiant_id and self.etudiant.role != self.etudiant.Role.ETUDIANT:
            erreurs["etudiant"] = "Le compte doit avoir le role etudiant."
        if self.cours_id and self.periode_id:
            if self.cours.programme.entite_id != self.periode.entite_id:
                erreurs["periode"] = (
                    "Le cours et la periode doivent appartenir a la meme entite."
                )
        if self.etudiant_id and self.cours_id and self.periode_id:
            inscription_validee = self.etudiant.inscriptions_pedagogiques.filter(
                programme_id=self.cours.programme_id,
                periode_id=self.periode_id,
                statut="validee",
                conditions_passage_verifiees=True,
                cours_selectionnes__cours_id=self.cours_id,
            ).exists()
            if not inscription_validee:
                erreurs["etudiant"] = (
                    "L'etudiant doit etre inscrit et valide a ce cours pour cette periode."
                )
        if self.saisie_par_id and self.cours_id and self.periode_id:
            if self.saisie_par.role == self.saisie_par.Role.PROFESSEUR:
                from applications.referentiels.models import AffectationCours

                affectation_valide = AffectationCours.objects.filter(
                    professeur=self.saisie_par,
                    cours=self.cours,
                    periode=self.periode,
                ).exists()
                if not affectation_valide:
                    erreurs["saisie_par"] = (
                        "Le professeur n'est pas affecte a ce cours pour cette periode."
                    )
            elif not self.saisie_par.is_superuser:
                if self.saisie_par.role != self.saisie_par.Role.PERSONNEL:
                    erreurs["saisie_par"] = (
                        "Seul un professeur ou le registrariat peut saisir une note."
                    )
                elif self.saisie_par.entite_id != self.cours.programme.entite_id:
                    erreurs["saisie_par"] = (
                        "Le registrariat doit appartenir a la meme entite."
                    )
        if erreurs:
            raise ValidationError(erreurs)

    def __str__(self):
        return f"{self.etudiant} - {self.cours} - {self.libelle}"


class ProgrammationExamen(models.Model):
    class Statut(models.TextChoices):
        PLANIFIE = "planifie", "Planifie"
        ANNULE = "annule", "Annule"

    cours = models.ForeignKey(
        "referentiels.Cours",
        verbose_name="cours",
        on_delete=models.PROTECT,
        related_name="examens_programmes",
    )
    periode = models.ForeignKey(
        "referentiels.PeriodeAcademique",
        verbose_name="periode academique",
        on_delete=models.PROTECT,
        related_name="examens_programmes",
    )
    libelle = models.CharField("examen", max_length=120)
    date_debut = models.DateTimeField("debut")
    date_fin = models.DateTimeField("fin")
    salle = models.CharField("salle", max_length=120)
    consignes = models.TextField("consignes", blank=True)
    statut = models.CharField(
        "statut", max_length=12, choices=Statut.choices, default=Statut.PLANIFIE
    )
    planifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="planifie par",
        on_delete=models.PROTECT,
        related_name="examens_planifies",
    )
    date_creation = models.DateTimeField("date de creation", auto_now_add=True)
    date_modification = models.DateTimeField("date de modification", auto_now=True)

    class Meta:
        ordering = ("date_debut", "cours__code")
        verbose_name = "examen programme"
        verbose_name_plural = "examens programmes"

    def clean(self):
        erreurs = {}
        if self.cours_id and self.periode_id:
            if self.cours.programme.entite_id != self.periode.entite_id:
                erreurs["periode"] = (
                    "Le cours et la periode doivent appartenir a la meme entite."
                )
        if self.date_debut and self.date_fin and self.date_fin <= self.date_debut:
            erreurs["date_fin"] = "La fin doit etre posterieure au debut."
        if (
            self.cours_id
            and self.date_debut
            and self.date_fin
            and self.statut == self.Statut.PLANIFIE
        ):
            chevauchements = ProgrammationExamen.objects.filter(
                cours__programme__entite_id=self.cours.programme.entite_id,
                statut=self.Statut.PLANIFIE,
                date_debut__lt=self.date_fin,
                date_fin__gt=self.date_debut,
            ).exclude(pk=self.pk)
            if chevauchements.filter(salle__iexact=self.salle).exists():
                erreurs["salle"] = "Cette salle est deja utilisee pendant ce creneau."
            if chevauchements.filter(cours=self.cours, periode=self.periode).exists():
                erreurs["date_debut"] = (
                    "Un autre examen est deja programme pour ce cours et cette periode."
                )
        if self.planifie_par_id and self.cours_id:
            if not self.planifie_par.is_superuser:
                if self.planifie_par.role != self.planifie_par.Role.PERSONNEL:
                    erreurs["planifie_par"] = (
                        "Seul le Registrariat peut programmer un examen."
                    )
                elif self.planifie_par.entite_id != self.cours.programme.entite_id:
                    erreurs["planifie_par"] = (
                        "Le Registrariat doit appartenir a la meme entite."
                    )
        if erreurs:
            raise ValidationError(erreurs)

    def __str__(self):
        return f"{self.libelle} - {self.cours} - {self.periode}"
