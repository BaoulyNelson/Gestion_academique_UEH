from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Entite(models.Model):
    code = models.CharField("code", max_length=20, unique=True)
    nom = models.CharField("nom", max_length=200)
    email_contact = models.EmailField("adresse de contact", blank=True)
    active = models.BooleanField("active", default=True)
    inscription_ouverte = models.BooleanField("inscriptions ouvertes", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "entité"
        verbose_name_plural = "entités"

    def __str__(self):
        return f"{self.code} - {self.nom}"


class Option(models.Model):
    entite = models.ForeignKey(
        Entite, on_delete=models.CASCADE, related_name="options", verbose_name="entité"
    )
    nom = models.CharField("nom", max_length=200)
    active = models.BooleanField("active", default=True)

    class Meta:
        ordering = ["nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["entite", "nom"], name="option_nom_unique_par_entite"
            )
        ]
        verbose_name = "option"
        verbose_name_plural = "options"

    def __str__(self):
        return self.nom


class Salle(models.Model):
    entite = models.ForeignKey(
        Entite, on_delete=models.CASCADE, related_name="salles", verbose_name="entité"
    )
    nom = models.CharField("nom", max_length=100)
    capacite = models.PositiveIntegerField("capacité", default=0)

    class Meta:
        ordering = ["nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["entite", "nom"], name="salle_nom_unique_par_entite"
            )
        ]
        verbose_name = "salle"
        verbose_name_plural = "salles"

    def __str__(self):
        return self.nom


class AdministrateurEntite(models.Model):
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="administration_entite",
        verbose_name="utilisateur",
    )
    entite = models.ForeignKey(
        Entite,
        on_delete=models.CASCADE,
        related_name="administrateurs",
        verbose_name="entité",
    )

    class Meta:
        verbose_name = "administrateur d’entité"
        verbose_name_plural = "administrateurs d’entité"

    def __str__(self):
        return f"{self.utilisateur} - {self.entite}"


def entites_autorisees(utilisateur):
    if not utilisateur.is_authenticated:
        return Entite.objects.none()
    if utilisateur.is_superuser:
        return None
    entites = Entite.objects.filter(administrateurs__utilisateur=utilisateur)
    if utilisateur.role == "personnel" and utilisateur.entite_id:
        entites = entites | Entite.objects.filter(code=utilisateur.entite.code)
    return entites.distinct()


def valider_appartenance(entite, option=None, salle=None):
    if option and option.entite_id != entite.pk:
        raise ValidationError(
            {"option": "Cette option n’appartient pas à l’entité sélectionnée."}
        )
    if salle and salle.entite_id != entite.pk:
        raise ValidationError(
            {"salle": "Cette salle n’appartient pas à l’entité sélectionnée."}
        )


class HoraireEntite(models.Model):
    class Code(models.TextChoices):
        AM = "AM", "AM"
        PM = "PM", "PM"

    entite = models.ForeignKey(
        Entite,
        on_delete=models.CASCADE,
        related_name="horaires",
        verbose_name="entité",
    )
    code = models.CharField("horaire", max_length=2, choices=Code.choices)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entite", "code"], name="horaire_unique_par_entite"
            )
        ]
        verbose_name = "horaire d’entité"
        verbose_name_plural = "horaires des entités"

    def __str__(self):
        return f"{self.entite} - {self.get_code_display()}"
