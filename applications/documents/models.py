from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from applications.candidats.models import Candidat


def valider_taille_document(fichier):
    if fichier.size > 2 * 1024 * 1024:
        raise ValidationError("La taille maximale autorisée est de 2 Mo.")


def valider_taille_photo_identite(fichier):
    if fichier.size > 1024 * 1024:
        raise ValidationError("La taille maximale de la photo est de 1 Mo.")


def valider_taille_identifiant(fichier):
    if fichier.size > 1024 * 1024:
        raise ValidationError("La taille maximale du document NIF/NINU est de 1 Mo.")


def valider_taille_certificat_scolaire(fichier):
    if fichier.size > 1024 * 1024:
        raise ValidationError("La taille maximale du certificat scolaire est de 1 Mo.")


def valider_taille_document_etude(fichier):
    if fichier.size > 4 * 1024 * 1024:
        raise ValidationError("La taille maximale de ce document est de 4 Mo.")


class DocumentCandidat(models.Model):
    class TypeDocument(models.TextChoices):
        NAISSANCE = "NAISSANCE", "Certificat de naissance"
        PHOTO = "PHOTO", "Photo d’identité"
        DIPLOME = "DIPLOME", "Diplôme ou relevé de notes"
        PAIEMENT = "PAIEMENT", "Fiche de paiement"
        NIF = "NIF", "Document NIF"
        NINU = "NINU", "Document NINU"
        AUTRE = "AUTRE", "Autre document"

    candidat = models.ForeignKey(
        Candidat,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="candidat",
    )
    type_document = models.CharField(
        "type de document", max_length=12, choices=TypeDocument.choices
    )
    fichier = models.FileField(
        "fichier",
        upload_to="documents_candidats/%Y/%m/",
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_document,
        ],
    )
    date_televersement = models.DateTimeField(
        "date de téléversement", auto_now_add=True
    )

    class Meta:
        ordering = ["-date_televersement"]
        verbose_name = "document de candidat"
        verbose_name_plural = "documents des candidats"

    def __str__(self):
        return f"{self.get_type_document_display()} - {Path(self.fichier.name).name}"
