from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class DossierEtudes(models.Model):
    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "Etudes en cours"
        FERME = "ferme", "Dossier ferme"
        ABANDON = "abandon", "Abandon"
        DIPLOME = "diplome", "Diplome"

    etudiant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="etudiant",
        on_delete=models.PROTECT,
        related_name="dossiers_etudes",
    )
    programme = models.ForeignKey(
        "referentiels.Programme",
        verbose_name="programme",
        on_delete=models.PROTECT,
        related_name="dossiers_etudes",
    )
    statut = models.CharField(
        "statut du dossier",
        max_length=12,
        choices=Statut.choices,
        default=Statut.EN_COURS,
    )
    date_ouverture = models.DateField("date d'ouverture")
    date_cloture = models.DateField("date de fermeture", null=True, blank=True)
    motif_cloture = models.CharField("motif de fermeture", max_length=240, blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cree par",
        on_delete=models.PROTECT,
        related_name="dossiers_crees",
    )
    date_creation = models.DateTimeField("date de creation", auto_now_add=True)

    class Meta:
        ordering = ("programme__nom", "etudiant__last_name")
        constraints = [
            models.UniqueConstraint(
                fields=("etudiant", "programme"), name="uniq_dossier_etudiant_programme"
            )
        ]
        verbose_name = "dossier d'etudes"
        verbose_name_plural = "dossiers d'etudes"

    def clean(self):
        erreurs = {}
        if self.etudiant_id and self.etudiant.role != self.etudiant.Role.ETUDIANT:
            erreurs["etudiant"] = "Le compte doit avoir le role etudiant."
        if self.etudiant_id and self.programme_id:
            if self.etudiant.entite_id != self.programme.entite_id:
                erreurs["programme"] = (
                    "Le programme doit appartenir a l'entite de l'etudiant."
                )
        if (
            self.date_cloture
            and self.date_ouverture
            and self.date_cloture < self.date_ouverture
        ):
            erreurs["date_cloture"] = (
                "La fermeture ne peut preceder l'ouverture du dossier."
            )
        if self.statut != self.Statut.EN_COURS and not self.date_cloture:
            erreurs["date_cloture"] = "La date de fermeture est requise pour ce statut."
        if self.cree_par_id and not self.cree_par.is_superuser:
            if self.cree_par.role != self.cree_par.Role.PERSONNEL:
                erreurs["cree_par"] = (
                    "Seul le registrariat peut creer un dossier d'etudes."
                )
            elif (
                self.programme_id
                and self.cree_par.entite_id != self.programme.entite_id
            ):
                erreurs["cree_par"] = (
                    "Le registrariat doit appartenir a la meme entite."
                )
        if erreurs:
            raise ValidationError(erreurs)

    def __str__(self):
        return f"{self.etudiant} - {self.programme}"


class ActeAcademique(models.Model):
    class TypeActe(models.TextChoices):
        ATTESTATION_INSCRIPTION = "attestation_inscription", "Attestation d'inscription"
        ATTESTATION_ETUDES = "attestation_etudes", "Attestation d'etudes"
        CERTIFICAT = "certificat", "Certificat d'etudes"
        RELEVE_NOTES = "releve_notes", "Releve de notes"
        DIPLOME = "diplome", "Diplome"

    etudiant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="etudiant",
        on_delete=models.PROTECT,
        related_name="actes_academiques",
    )
    programme = models.ForeignKey(
        "referentiels.Programme",
        verbose_name="programme",
        on_delete=models.PROTECT,
        related_name="actes_academiques",
    )
    periode = models.ForeignKey(
        "referentiels.PeriodeAcademique",
        verbose_name="periode academique",
        on_delete=models.PROTECT,
        related_name="actes_academiques",
    )
    type_acte = models.CharField("type d'acte", max_length=32, choices=TypeActe.choices)
    reference = models.CharField("reference officielle", max_length=80, unique=True)
    est_annule = models.BooleanField("annule", default=False)
    date_delivrance = models.DateField("date de delivrance")
    delivre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="delivre par",
        on_delete=models.PROTECT,
        related_name="actes_delivres",
    )
    date_creation = models.DateTimeField("date d'enregistrement", auto_now_add=True)

    class Meta:
        ordering = ("-date_delivrance", "reference")
        verbose_name = "acte academique"
        verbose_name_plural = "actes academiques"

    def clean(self):
        erreurs = {}
        if self.etudiant_id and self.etudiant.role != self.etudiant.Role.ETUDIANT:
            erreurs["etudiant"] = "Le compte doit avoir le role etudiant."
        if self.programme_id and self.periode_id:
            if self.programme.entite_id != self.periode.entite_id:
                erreurs["periode"] = (
                    "Le programme et la periode doivent appartenir a la meme entite."
                )
        if self.etudiant_id and self.programme_id:
            if self.etudiant.entite_id != self.programme.entite_id:
                erreurs["programme"] = (
                    "Le programme doit appartenir a l'entite de l'etudiant."
                )
        if self.etudiant_id and self.programme_id and self.periode_id:
            if self.type_acte == self.TypeActe.ATTESTATION_INSCRIPTION:
                from applications.inscriptions.models import InscriptionPedagogique

                existe = InscriptionPedagogique.objects.filter(
                    etudiant=self.etudiant,
                    programme=self.programme,
                    periode=self.periode,
                    statut=InscriptionPedagogique.Statut.VALIDEE,
                ).exists()
                if not existe:
                    erreurs["type_acte"] = (
                        "Une attestation d'inscription exige une inscription validee."
                    )
            elif self.type_acte in {
                self.TypeActe.ATTESTATION_ETUDES,
                self.TypeActe.RELEVE_NOTES,
            }:
                from applications.notes.models import Evaluation

                existe = Evaluation.objects.filter(
                    etudiant=self.etudiant,
                    cours__programme=self.programme,
                    periode=self.periode,
                    est_publiee=True,
                ).exists()
                if not existe:
                    erreurs["type_acte"] = (
                        "Un releve exige au moins une evaluation publiee pour cette periode."
                    )
            elif self.type_acte == self.TypeActe.DIPLOME:
                existe = DossierEtudes.objects.filter(
                    etudiant=self.etudiant,
                    programme=self.programme,
                    statut=DossierEtudes.Statut.DIPLOME,
                ).exists()
                if not existe:
                    erreurs["type_acte"] = (
                        "Un diplome exige un dossier d'etudes au statut diplome."
                    )
        if self.delivre_par_id and not self.delivre_par.is_superuser:
            if self.delivre_par.role != self.delivre_par.Role.PERSONNEL:
                erreurs["delivre_par"] = (
                    "Seul le registrariat peut delivrer un acte academique."
                )
            elif (
                self.programme_id
                and self.delivre_par.entite_id != self.programme.entite_id
            ):
                erreurs["delivre_par"] = (
                    "Le registrariat doit appartenir a la meme entite."
                )
        if erreurs:
            raise ValidationError(erreurs)

    def __str__(self):
        return f"{self.reference} - {self.get_type_acte_display()}"


class SoutenanceMemoire(models.Model):
    class Statut(models.TextChoices):
        PLANIFIEE = "planifiee", "Planifiee"
        SOUTENUE = "soutenue", "Soutenue"
        ANNULEE = "annulee", "Annulee"

    etudiant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="etudiant",
        on_delete=models.PROTECT,
        related_name="soutenances_memoire",
    )
    programme = models.ForeignKey(
        "referentiels.Programme",
        verbose_name="programme",
        on_delete=models.PROTECT,
        related_name="soutenances_memoire",
    )
    periode = models.ForeignKey(
        "referentiels.PeriodeAcademique",
        verbose_name="periode academique",
        on_delete=models.PROTECT,
        related_name="soutenances_memoire",
    )
    titre = models.CharField("titre du memoire", max_length=240)
    date_soutenance = models.DateField("date de soutenance")
    statut = models.CharField(
        "statut", max_length=12, choices=Statut.choices, default=Statut.PLANIFIEE
    )
    note = models.DecimalField(
        "note sur 100",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    jury = models.TextField("membres du jury", blank=True)
    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="enregistre par",
        on_delete=models.PROTECT,
        related_name="soutenances_enregistrees",
    )
    date_creation = models.DateTimeField("date de creation", auto_now_add=True)

    class Meta:
        ordering = ("-date_soutenance", "etudiant__last_name")
        constraints = [
            models.UniqueConstraint(
                fields=("etudiant", "programme", "titre"),
                name="uniq_soutenance_etudiant_programme_titre",
            )
        ]
        verbose_name = "soutenance de memoire"
        verbose_name_plural = "soutenances de memoire"

    def clean(self):
        erreurs = {}
        if self.etudiant_id and self.etudiant.role != self.etudiant.Role.ETUDIANT:
            erreurs["etudiant"] = "Le compte doit avoir le role etudiant."
        if self.programme_id and self.periode_id:
            if self.programme.entite_id != self.periode.entite_id:
                erreurs["periode"] = (
                    "Le programme et la periode doivent appartenir a la meme entite."
                )
        if self.enregistre_par_id and not self.enregistre_par.is_superuser:
            if self.enregistre_par.role != self.enregistre_par.Role.PERSONNEL:
                erreurs["enregistre_par"] = (
                    "Seul le registrariat peut enregistrer une soutenance."
                )
            elif (
                self.programme_id
                and self.enregistre_par.entite_id != self.programme.entite_id
            ):
                erreurs["enregistre_par"] = (
                    "Le registrariat doit appartenir a la meme entite."
                )
        if self.statut == self.Statut.SOUTENUE and self.note is None:
            erreurs["note"] = "La note est requise apres la soutenance."
        if erreurs:
            raise ValidationError(erreurs)

    def __str__(self):
        return f"{self.etudiant} - {self.titre}"
