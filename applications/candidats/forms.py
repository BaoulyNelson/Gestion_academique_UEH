import csv
import re
from functools import lru_cache

from django import forms
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from applications.candidats.models import Candidat
from applications.candidatures.progression import CHAMPS_PROFIL_REQUIS
from applications.documents.models import DocumentCandidat, valider_taille_document


@lru_cache(maxsize=1)
def choix_communes():
    chemin_departements = settings.BASE_DIR / "data" / "departements.csv"
    with chemin_departements.open(encoding="utf-8", newline="") as fichier:
        departements = {ligne["id"]: ligne["nom"] for ligne in csv.DictReader(fichier)}

    chemin_communes = settings.BASE_DIR / "data" / "communes.csv"
    with chemin_communes.open(encoding="utf-8", newline="") as fichier:
        choix = [
            (
                ligne["nom"],
                f"{ligne['nom']} ({departements.get(ligne['departement_id'], 'Haïti')})",
            )
            for ligne in csv.DictReader(fichier)
        ]
    return [("", "Sélectionner une commune")] + choix


class NINUField(forms.RegexField):
    def __init__(self, **kwargs):
        kwargs.setdefault("regex", r"^[0-9]{1,10}$")
        kwargs.setdefault("max_length", 10)
        kwargs.setdefault("required", False)
        kwargs.setdefault(
            "widget",
            forms.TextInput(
                attrs={
                    "class": "form-control",
                    "inputmode": "numeric",
                    "maxlength": "10",
                    "pattern": "[0-9]{1,10}",
                    "autocomplete": "off",
                    "title": "Saisissez entre 1 et 10 chiffres.",
                }
            ),
        )
        kwargs.setdefault(
            "error_messages",
            {
                "invalid": "Le NINU doit contenir uniquement des chiffres, 10 au maximum.",
                "max_length": "Le NINU ne peut pas dépasser 10 chiffres.",
            },
        )
        super().__init__(**kwargs)

    @staticmethod
    def valeur_valide(valeur):
        return not valeur or bool(re.fullmatch(r"[0-9]{1,10}", valeur))


class ProfilCandidatForm(forms.ModelForm):
    ninu = NINUField(label="NINU")

    prenom = forms.CharField(
        label="Prénom",
        max_length=100,
        disabled=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    nom = forms.CharField(
        label="Nom",
        max_length=100,
        disabled=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label="E-mail",
        required=False,
        disabled=True,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    document_naissance = forms.FileField(
        label="Acte de naissance",
        required=False,
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_document,
        ],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
        ),
    )
    photo_identite = forms.FileField(
        label="Photo d’identité",
        required=False,
        validators=[
            FileExtensionValidator(["jpg", "jpeg"]),
            valider_taille_document,
        ],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".jpg,.jpeg"}
        ),
    )
    document_ninu = forms.FileField(
        label="Document NINU",
        required=False,
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_document,
        ],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
        ),
    )
    document_nif = forms.FileField(
        label="Document NIF",
        required=False,
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_document,
        ],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
        ),
    )

    class Meta:
        model = Candidat
        fields = [
            "nationalite",
            "telephone",
            "date_naissance",
            "lieu_naissance",
            "nom_parent_responsable",
            "nif",
            "ninu",
            "adresse",
            "ville",
            "sexe",
            "departement_geographique",
            "etablissement_scolaire",
            "annee_obtention",
        ]
        widgets = {
            "nationalite": forms.TextInput(attrs={"class": "form-control"}),
            "telephone": forms.TextInput(attrs={"class": "form-control"}),
            "date_naissance": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "lieu_naissance": forms.Select(attrs={"class": "form-select"}),
            "nom_parent_responsable": forms.TextInput(attrs={"class": "form-control"}),
            "nif": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "000-000-000-0"}
            ),
            "adresse": forms.TextInput(attrs={"class": "form-control"}),
            "ville": forms.TextInput(attrs={"class": "form-control"}),
            "sexe": forms.Select(attrs={"class": "form-select"}),
            "departement_geographique": forms.Select(attrs={"class": "form-select"}),
            "etablissement_scolaire": forms.TextInput(attrs={"class": "form-control"}),
            "annee_obtention": forms.NumberInput(
                attrs={"class": "form-control", "min": 1950, "max": 2100}
            ),
        }

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        self.utilisateur = utilisateur
        for champ in CHAMPS_PROFIL_REQUIS:
            self.fields[champ].required = True
        self.fields["lieu_naissance"].choices = choix_communes()
        valeur_actuelle = self.instance.lieu_naissance
        if valeur_actuelle and valeur_actuelle not in dict(
            self.fields["lieu_naissance"].choices
        ):
            self.fields["lieu_naissance"].choices += (
                (valeur_actuelle, valeur_actuelle),
            )
        self.fields["sexe"].label = "Genre"
        self.fields["sexe"].required = True
        self.fields["nationalite"].initial = self.instance.nationalite or "Haïtienne"
        self.fields["nom_parent_responsable"].label = (
            "Nom et prénom d’un parent ou d’une personne responsable"
        )
        self.fields["nom_parent_responsable"].help_text = (
            "Requis si vous avez moins de 18 ans."
        )
        self.fields["nif"].required = False
        self.fields["ninu"].required = False
        if not self.is_bound and not NINUField.valeur_valide(self.instance.ninu):
            self.initial["ninu"] = ""
            self.fields["ninu"].help_text = (
                "La valeur enregistrée est invalide. Saisissez un NINU de 10 chiffres au maximum."
            )
        self.fields["nif"].help_text = (
            "Saisissez le NIF ou le NINU, au moins l’un des deux."
        )
        self.fields["ninu"].help_text = (
            "Saisissez le NINU ou le NIF, au moins l’un des deux."
        )
        types_existants = set()
        if self.instance.pk:
            types_existants = set(
                self.instance.documents.values_list("type_document", flat=True)
            )
        self.fields["document_naissance"].required = (
            DocumentCandidat.TypeDocument.NAISSANCE not in types_existants
        )
        self.fields["photo_identite"].required = (
            DocumentCandidat.TypeDocument.PHOTO not in types_existants
        )
        self.fields["prenom"].help_text = (
            "Prénom du compte utilisateur (non modifiable)."
        )
        self.fields["nom"].help_text = "Nom du compte utilisateur (non modifiable)."
        self.fields["email"].help_text = (
            "Adresse du compte utilisateur (non modifiable)."
        )
        self.fields["prenom"].initial = utilisateur.prenom
        self.fields["nom"].initial = utilisateur.nom
        self.fields["email"].initial = utilisateur.email

    def clean(self):
        donnees = super().clean()
        nif = donnees.get("nif", "").strip()
        ninu = donnees.get("ninu", "").strip()
        if not nif and not ninu:
            self.add_error("nif", "Saisissez au moins un NIF ou un NINU.")

        naissance = donnees.get("date_naissance")
        if naissance:
            aujourd_hui = timezone.localdate()
            age = (
                aujourd_hui.year
                - naissance.year
                - (
                    (aujourd_hui.month, aujourd_hui.day)
                    < (naissance.month, naissance.day)
                )
            )
            if age < 18 and not donnees.get("nom_parent_responsable", "").strip():
                self.add_error(
                    "nom_parent_responsable",
                    "Indiquez le nom d’un parent ou d’une personne responsable.",
                )

        types_existants = set()
        if self.instance.pk:
            types_existants = set(
                self.instance.documents.values_list("type_document", flat=True)
            )
        documents_personnels = (
            ("document_naissance", DocumentCandidat.TypeDocument.NAISSANCE),
            ("photo_identite", DocumentCandidat.TypeDocument.PHOTO),
        )
        for champ, type_document in documents_personnels:
            if not donnees.get(champ) and type_document not in types_existants:
                self.add_error(champ, "Ce document est obligatoire.")

        documents_identite = {
            "document_nif": ("nif", DocumentCandidat.TypeDocument.NIF),
            "document_ninu": ("ninu", DocumentCandidat.TypeDocument.NINU),
        }
        identifiant_justifie = any(
            donnees.get(champ_identifiant)
            and (donnees.get(champ_document) or type_document in types_existants)
            for champ_document, (
                champ_identifiant,
                type_document,
            ) in documents_identite.items()
        )
        if (nif or ninu) and not identifiant_justifie:
            self.add_error(
                "document_nif",
                "Téléversez le justificatif correspondant au NIF ou au NINU saisi.",
            )
        return donnees

    def save(self, commit=True):
        candidat = super().save(commit=False)
        self.utilisateur.prenom = self.cleaned_data["prenom"]
        self.utilisateur.nom = self.cleaned_data["nom"]
        if commit:
            self.utilisateur.save(update_fields=["prenom", "nom"])
            candidat.save()
            correspondances = (
                ("document_naissance", DocumentCandidat.TypeDocument.NAISSANCE),
                ("photo_identite", DocumentCandidat.TypeDocument.PHOTO),
                ("document_nif", DocumentCandidat.TypeDocument.NIF),
                ("document_ninu", DocumentCandidat.TypeDocument.NINU),
            )
            for champ, type_document in correspondances:
                fichier = self.cleaned_data.get(champ)
                if not fichier:
                    continue
                document = candidat.documents.filter(
                    type_document=type_document
                ).first()
                if document:
                    document.fichier = fichier
                    document.save(update_fields=["fichier", "date_televersement"])
                else:
                    DocumentCandidat.objects.create(
                        candidat=candidat,
                        type_document=type_document,
                        fichier=fichier,
                    )
        return candidat
