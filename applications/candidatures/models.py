import re

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.db.models import Q

from applications.candidats.models import Candidat
from applications.entites.models import (
    Entite,
    Option,
    Salle,
    HoraireEntite,
    entites_autorisees,
    valider_appartenance,
)
from applications.documents.models import valider_taille_document


class GestionnaireInscriptions(models.QuerySet):
    champs_proteges = {
        "numero_dossier",
        "rang",
        "candidat",
        "candidat_id",
        "entite",
        "entite_id",
        "option",
        "option_id",
        "salle",
        "salle_id",
        "horaire",
    }

    def update(self, **kwargs):
        if self.champs_proteges.intersection(kwargs):
            raise ValidationError(
                "Les champs protégés doivent être modifiés par le parcours validé."
            )
        return super().update(**kwargs)

    def bulk_create(self, objets, **kwargs):
        if objets:
            raise ValidationError(
                "Les inscriptions doivent être créées une par une pour garantir leur numéro de dossier."
            )
        return super().bulk_create(objets, **kwargs)

    def bulk_update(self, objets, champs, **kwargs):
        if self.champs_proteges.intersection(champs):
            raise ValidationError(
                "Les champs protégés ne peuvent pas être modifiés en lot."
            )
        return super().bulk_update(objets, champs, **kwargs)

    def pour_utilisateur(self, utilisateur):
        autorisees = entites_autorisees(utilisateur)
        return self if autorisees is None else self.filter(entite__in=autorisees)


class Inscription(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente de validation"
        VALIDE = "VALIDE", "Validé"
        REJETE = "REJETE", "Rejeté"

    class Horaire(models.TextChoices):
        AM = "AM", "AM"
        PM = "PM", "PM"

    candidat = models.ForeignKey(
        Candidat,
        on_delete=models.CASCADE,
        related_name="inscriptions",
        verbose_name="candidat",
    )
    entite = models.ForeignKey(
        Entite,
        on_delete=models.PROTECT,
        related_name="inscriptions",
        verbose_name="entité",
    )
    option = models.ForeignKey(
        Option,
        on_delete=models.PROTECT,
        related_name="inscriptions",
        null=True,
        blank=True,
        verbose_name="option",
    )
    annee_academique = models.CharField("année académique", max_length=9)
    horaire = models.CharField(
        "horaire", max_length=2, choices=Horaire.choices, blank=True
    )
    seq = models.CharField("Seq", max_length=50, blank=True)
    till = models.CharField("Till", max_length=50, blank=True)
    date_depot = models.DateField("date de dépôt", null=True, blank=True)
    recu_paiement = models.FileField(
        "reçu de paiement",
        upload_to="documents_candidats/paiements/%Y/%m/",
        blank=True,
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_document,
        ],
    )
    date_inscription = models.DateTimeField("date d’inscription", auto_now_add=True)
    salle = models.ForeignKey(
        Salle,
        on_delete=models.SET_NULL,
        related_name="inscriptions",
        null=True,
        blank=True,
        verbose_name="salle",
    )
    statut = models.CharField(
        "statut", max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE
    )
    numero_dossier = models.PositiveBigIntegerField(
        "numéro de dossier", unique=True, editable=False
    )
    rang = models.PositiveSmallIntegerField("rang", editable=False)

    objects = GestionnaireInscriptions.as_manager()

    class Meta:
        ordering = ["-date_inscription", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidat", "rang"], name="inscription_rang_unique_par_candidat"
            ),
            models.CheckConstraint(
                check=Q(rang__gte=0) & Q(rang__lte=2),
                name="inscription_rang_entre_zero_et_deux",
            ),
        ]
        indexes = [
            models.Index(fields=["entite", "statut"]),
            models.Index(fields=["candidat", "annee_academique"]),
        ]
        verbose_name = "inscription"
        verbose_name_plural = "inscriptions"

    def clean(self):
        super().clean()
        if self.entite_id:
            if (
                self._state.adding
                and self.candidat_id
                and type(self)
                .objects.filter(candidat_id=self.candidat_id, entite_id=self.entite_id)
                .exists()
            ):
                raise ValidationError(
                    {"entite": "Vous avez déjà une inscription pour cette entité."}
                )
            if self._state.adding and not self.entite.inscription_ouverte:
                raise ValidationError(
                    {"entite": "Les inscriptions sont fermées pour cette entité."}
                )
            valider_appartenance(self.entite, self.option, self.salle)
            if self.horaire:
                horaires = HoraireEntite.objects.filter(
                    entite_id=self.entite_id, code=self.horaire
                )
                if self._state.adding:
                    horaires = horaires.filter(actif=True)
                if not horaires.exists():
                    raise ValidationError(
                        {
                            "horaire": "Cet horaire n’est pas proposé par l’entité choisie."
                        }
                    )
        if self.annee_academique and not re.fullmatch(
            r"\d{4}-\d{4}", self.annee_academique
        ):
            raise ValidationError(
                {"annee_academique": "Saisissez une année au format 2026-2027."}
            )

    def save(self, *args, **kwargs):
        if self.pk:
            ancienne = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("numero_dossier", "rang", "candidat_id")
                .first()
            )
            if ancienne and (
                ancienne["numero_dossier"] != self.numero_dossier
                or ancienne["rang"] != self.rang
                or ancienne["candidat_id"] != self.candidat_id
            ):
                raise ValidationError(
                    "Le candidat, le rang et le numéro de dossier sont immuables."
                )
            self.full_clean()
            return super().save(*args, **kwargs)

        with transaction.atomic():
            candidat_verrouille = Candidat.objects.select_for_update().get(
                pk=self.candidat_id
            )
            rangs = set(
                type(self)
                .objects.filter(candidat=candidat_verrouille)
                .values_list("rang", flat=True)
            )
            rang_libre = next((rang for rang in range(3) if rang not in rangs), None)
            if rang_libre is None:
                raise ValidationError(
                    "Vous avez atteint la limite de 3 inscriptions autorisées."
                )
            self.rang = rang_libre
            self.numero_dossier = candidat_verrouille.pk * 100 + rang_libre
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"#{self.numero_dossier or 'en création'} - {self.entite}"


class BrouillonInscription(models.Model):
    candidat = models.OneToOneField(
        Candidat,
        on_delete=models.CASCADE,
        related_name="brouillon_inscription",
        verbose_name="candidat",
    )
    entite = models.ForeignKey(
        Entite,
        on_delete=models.SET_NULL,
        related_name="brouillons_inscription",
        null=True,
        blank=True,
        verbose_name="entité",
    )
    option = models.ForeignKey(
        Option,
        on_delete=models.SET_NULL,
        related_name="brouillons_inscription",
        null=True,
        blank=True,
        verbose_name="option",
    )
    annee_academique = models.CharField("année académique", max_length=9, blank=True)
    horaire = models.CharField(
        "horaire", max_length=2, choices=Inscription.Horaire.choices, blank=True
    )
    seq = models.CharField("Seq", max_length=50, blank=True)
    till = models.CharField("Till", max_length=50, blank=True)
    date_depot = models.DateField("date de dépôt", null=True, blank=True)
    recu_paiement = models.FileField(
        "reçu de paiement",
        upload_to="documents_candidats/paiements/%Y/%m/",
        blank=True,
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_document,
        ],
    )
    date_modification = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "brouillon d’inscription"
        verbose_name_plural = "brouillons d’inscription"

    def __str__(self):
        return f"Brouillon de {self.candidat}"
