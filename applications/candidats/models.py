from django.conf import settings
from django.db import models


class Candidat(models.Model):
    class Sexe(models.TextChoices):
        FEMININ = "FEMININ", "Féminin"
        MASCULIN = "MASCULIN", "Masculin"
        AUTRE = "AUTRE", "Autre"

    class Departement(models.TextChoices):
        ARTIBONITE = "ARTIBONITE", "Artibonite"
        CENTRE = "CENTRE", "Centre"
        GRANDE_ANSE = "GRANDE_ANSE", "Grande-Anse"
        NIPPES = "NIPPES", "Nippes"
        NORD = "NORD", "Nord"
        NORD_EST = "NORD_EST", "Nord-Est"
        NORD_OUEST = "NORD_OUEST", "Nord-Ouest"
        OUEST = "OUEST", "Ouest"
        SUD = "SUD", "Sud"
        SUD_EST = "SUD_EST", "Sud-Est"

    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profil_candidat",
        verbose_name="utilisateur",
    )
    nationalite = models.CharField("nationalité", max_length=80, default="Haïtienne")
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    date_naissance = models.DateField("date de naissance", null=True, blank=True)
    lieu_naissance = models.CharField("lieu de naissance", max_length=150, blank=True)
    nom_parent_responsable = models.CharField(
        "nom du parent ou responsable", max_length=200, blank=True
    )
    nif = models.CharField("NIF", max_length=30, blank=True)
    ninu = models.CharField("NINU", max_length=30, blank=True)
    adresse = models.CharField("adresse", max_length=255, blank=True)
    ville = models.CharField("ville", max_length=100, blank=True)
    sexe = models.CharField(
        "sexe (facultatif)", max_length=10, choices=Sexe.choices, blank=True
    )
    departement_geographique = models.CharField(
        "département géographique (facultatif)",
        max_length=15,
        choices=Departement.choices,
        blank=True,
    )
    etablissement_scolaire = models.CharField(
        "établissement scolaire", max_length=200, blank=True
    )
    annee_obtention = models.PositiveSmallIntegerField(
        "année d’obtention", null=True, blank=True
    )
    date_creation = models.DateTimeField("date de création", auto_now_add=True)

    class Meta:
        verbose_name = "candidat"
        verbose_name_plural = "candidats"

    def __str__(self):
        return (
            f"{self.utilisateur.prenom} {self.utilisateur.nom}".strip()
            or self.utilisateur.email
        )

    @property
    def photo_identite(self):
        return self.documents.filter(type_document="PHOTO").first()


class EcoleCandidat(models.Model):
    candidat = models.ForeignKey(
        Candidat,
        on_delete=models.CASCADE,
        related_name="ecoles",
        verbose_name="candidat",
    )
    nom = models.CharField("nom de l’école", max_length=200)
    zone = models.CharField("commune", max_length=100, blank=True)
    certificat = models.FileField(
        "certificat scolaire",
        upload_to="dossiers_candidats/ecoles/%Y/%m/",
    )
    date_ajout = models.DateTimeField("ajouté le", auto_now_add=True)

    class Meta:
        ordering = ["-date_ajout", "pk"]
        verbose_name = "école de candidat"
        verbose_name_plural = "écoles du candidat"

    def __str__(self):
        return self.nom


class ParcoursCandidat(models.Model):
    class Niveau(models.TextChoices):
        LICENCE = "LICENCE", "Licence"
        MASTER = "MASTER", "Master"
        DOCTORAT = "DOCTORAT", "Doctorat"
        AUTRE = "AUTRE", "Autre"

    candidat = models.ForeignKey(
        Candidat,
        on_delete=models.CASCADE,
        related_name="parcours_etudes",
        verbose_name="candidat",
    )
    etablissement = models.CharField(
        "établissement d’enseignement supérieur", max_length=200
    )
    niveau = models.CharField(
        "niveau", max_length=12, choices=Niveau.choices, blank=True
    )
    programme = models.CharField("programme", max_length=200, blank=True)
    annee_obtention = models.PositiveSmallIntegerField(
        "année d’obtention", null=True, blank=True
    )
    type_document = models.CharField(
        "type de diplôme ou relevé", max_length=100, blank=True
    )
    certificat = models.FileField(
        "certificat ou relevé de notes",
        upload_to="dossiers_candidats/etudes/%Y/%m/",
        blank=True,
    )
    lettre_recommandation = models.FileField(
        "lettre de recommandation",
        upload_to="dossiers_candidats/etudes/%Y/%m/",
        blank=True,
    )
    lettre_motivation = models.FileField(
        "lettre de motivation",
        upload_to="dossiers_candidats/etudes/%Y/%m/",
        blank=True,
    )
    cv_ou_autre_document = models.FileField(
        "CV ou autre document",
        upload_to="dossiers_candidats/etudes/%Y/%m/",
        blank=True,
    )
    date_ajout = models.DateTimeField("ajouté le", auto_now_add=True)

    class Meta:
        ordering = ["-date_ajout", "pk"]
        verbose_name = "parcours d’études supérieures"
        verbose_name_plural = "parcours d’études supérieures"

    def __str__(self):
        return f"{self.etablissement} - {self.get_niveau_display() or 'Études'}"
