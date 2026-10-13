import csv
import re
from datetime import date

from django import forms
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from applications.candidats.forms import NINUField
from applications.candidats.models import (
    Candidat,
    EcoleCandidat,
    ParcoursCandidat,
)
from applications.documents.models import (
    DocumentCandidat,
    valider_taille_certificat_scolaire,
    valider_taille_document,
    valider_taille_document_etude,
    valider_taille_identifiant,
    valider_taille_photo_identite,
)

DEPARTEMENTS_CSV = {
    "ARTIBONITE": "1",
    "CENTRE": "2",
    "GRANDE_ANSE": "3",
    "NIPPES": "4",
    "NORD": "5",
    "NORD_EST": "6",
    "NORD_OUEST": "7",
    "OUEST": "8",
    "SUD_EST": "9",
    "SUD": "10",
}
NOMS_DEPARTEMENTS_CSV = {
    "1": "Artibonite",
    "2": "Centre",
    "3": "Grand’Anse",
    "4": "Nippes",
    "5": "Nord",
    "6": "Nord-Est",
    "7": "Nord-Ouest",
    "8": "Ouest",
    "9": "Sud-Est",
    "10": "Sud",
}


def lire_communes():
    chemin = settings.BASE_DIR / "data" / "communes.csv"
    with chemin.open(encoding="utf-8", newline="") as fichier:
        return list(csv.DictReader(fichier))


def choix_communes(departement=""):
    departement_id = DEPARTEMENTS_CSV.get(departement)
    communes = [
        (
            ligne["nom"],
            f"{ligne['nom']} ({NOMS_DEPARTEMENTS_CSV.get(ligne['departement_id'], 'Haïti')})",
        )
        for ligne in lire_communes()
        if not departement_id or ligne["departement_id"] == departement_id
    ]
    return [("", "Sélectionner une commune")] + communes


class InformationsPersonnellesForm(forms.ModelForm):
    ninu = NINUField(label="NINU")

    prenom = forms.CharField(
        label="Prénom",
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    nom = forms.CharField(
        label="Nom",
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label="E-mail",
        disabled=True,
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    lieu_naissance = forms.ChoiceField(
        choices=(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    document_naissance = forms.FileField(
        label="Acte de naissance",
        required=False,
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_identifiant,
        ],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
        ),
    )
    photo_identite = forms.FileField(
        label="Photo d’identité",
        required=False,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png"]),
            valider_taille_photo_identite,
        ],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".jpg,.jpeg,.png"}
        ),
    )
    document_ninu = forms.FileField(
        label="Document NINU",
        required=False,
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_identifiant,
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
            "sexe",
            "date_naissance",
            "nationalite",
            "telephone",
            "nom_parent_responsable",
            "lieu_naissance",
            "ninu",
            "nif",
        ]
        widgets = {
            "sexe": forms.Select(attrs={"class": "form-select"}),
            "date_naissance": forms.DateInput(
                attrs={"class": "form-control", "type": "date"},
                format="%Y-%m-%d",
            ),
            "nationalite": forms.TextInput(attrs={"class": "form-control"}),
            "telephone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+509 XX XX XXXX"}
            ),
            "nom_parent_responsable": forms.TextInput(attrs={"class": "form-control"}),
            "lieu_naissance": forms.Select(attrs={"class": "form-select"}),
            "nif": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "000-234-765-7",
                    "inputmode": "numeric",
                    "maxlength": "13",
                    "autocomplete": "off",
                }
            ),
        }

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        self.utilisateur = utilisateur
        self.fields["sexe"].label = "Genre"
        self.fields["sexe"].required = True
        self.fields["date_naissance"].required = True
        self.fields["nationalite"].required = True
        self.fields["telephone"].required = True
        self.fields["lieu_naissance"].label = (
            "Lieu de Naissance (Municipalité ou Commune)"
        )
        self.fields["lieu_naissance"].choices = choix_communes()
        if self.instance.lieu_naissance and self.instance.lieu_naissance not in dict(
            self.fields["lieu_naissance"].choices
        ):
            self.fields["lieu_naissance"].choices += (
                (self.instance.lieu_naissance, self.instance.lieu_naissance),
            )
        self.fields["nationalite"].initial = self.instance.nationalite or "Haïtienne"
        self.fields["nom_parent_responsable"].label = (
            "Nom et Prénom d’un parent ou d’une personne responsable"
        )
        self.fields["nom_parent_responsable"].required = False
        self.fields["nif"].required = False
        self.fields["ninu"].required = False
        if not self.is_bound and not NINUField.valeur_valide(self.instance.ninu):
            self.initial["ninu"] = ""
            self.fields["ninu"].help_text = (
                "La valeur enregistrée est invalide. Saisissez un NINU de 10 chiffres au maximum."
            )
        self.fields["prenom"].initial = utilisateur.prenom
        self.fields["nom"].initial = utilisateur.nom
        self.fields["email"].initial = utilisateur.email
        self.types_existants = set()
        if self.instance.pk:
            self.types_existants = set(
                self.instance.documents.values_list("type_document", flat=True)
            )
        self.fields["document_naissance"].required = (
            DocumentCandidat.TypeDocument.NAISSANCE not in self.types_existants
        )
        self.fields["photo_identite"].required = (
            DocumentCandidat.TypeDocument.PHOTO not in self.types_existants
        )

    def clean(self):
        donnees = super().clean()
        nif = (donnees.get("nif") or "").strip()
        ninu = (donnees.get("ninu") or "").strip()
        if bool(nif) == bool(ninu):
            self.add_error("nif", "Saisissez le NIF ou le NINU, mais pas les deux.")
        identifiant = "NIF" if nif else "NINU" if ninu else ""
        telephone = re.sub(r"\D", "", donnees.get("telephone", ""))
        if telephone.startswith("509"):
            telephone = telephone[3:]
        if telephone and len(telephone) != 8:
            self.add_error(
                "telephone", "Le téléphone doit contenir 8 chiffres après +509."
            )
        naissance = donnees.get("date_naissance")
        if naissance:
            aujourdhui = timezone.localdate()
            age = (
                aujourdhui.year
                - naissance.year
                - (
                    (aujourdhui.month, aujourdhui.day)
                    < (naissance.month, naissance.day)
                )
            )
            if age < 18 and not (donnees.get("nom_parent_responsable") or "").strip():
                self.add_error(
                    "nom_parent_responsable",
                    "Indiquez le nom et le prénom d’un parent ou d’une personne responsable.",
                )
        if identifiant == "NIF":
            self.fields["document_nif"].required = (
                DocumentCandidat.TypeDocument.NIF not in self.types_existants
            )
            if (
                not donnees.get("document_nif")
                and DocumentCandidat.TypeDocument.NIF not in self.types_existants
            ):
                self.add_error(
                    "document_nif", "Le justificatif du NIF est obligatoire."
                )
        elif identifiant == "NINU":
            self.fields["document_ninu"].required = (
                DocumentCandidat.TypeDocument.NINU not in self.types_existants
            )
            if (
                not donnees.get("document_ninu")
                and DocumentCandidat.TypeDocument.NINU not in self.types_existants
            ):
                self.add_error(
                    "document_ninu", "Le justificatif du NINU est obligatoire."
                )
        return donnees

    def clean_nif(self):
        nif = re.sub(r"\D", "", self.cleaned_data.get("nif", ""))
        if not nif:
            return ""
        if len(nif) != 10:
            raise forms.ValidationError("Le NIF doit contenir exactement 10 chiffres.")
        return f"{nif[:3]}-{nif[3:6]}-{nif[6:9]}-{nif[9]}"

    def save(self, commit=True):
        candidat = super().save(commit=False)
        if commit:
            candidat.save()
            for champ, type_document in (
                ("document_naissance", DocumentCandidat.TypeDocument.NAISSANCE),
                ("photo_identite", DocumentCandidat.TypeDocument.PHOTO),
                ("document_nif", DocumentCandidat.TypeDocument.NIF),
                ("document_ninu", DocumentCandidat.TypeDocument.NINU),
            ):
                fichier = self.cleaned_data.get(champ)
                if fichier:
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
            if self.cleaned_data.get("nif"):
                type_inactif = DocumentCandidat.TypeDocument.NINU
            else:
                type_inactif = DocumentCandidat.TypeDocument.NIF
            for ancien_document in candidat.documents.filter(
                type_document=type_inactif
            ):
                ancien_document.fichier.delete(save=False)
                ancien_document.delete()
        return candidat


class AdresseCandidatForm(forms.ModelForm):
    ville = forms.ChoiceField(
        label="Municipalité",
        choices=(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Candidat
        fields = ["adresse", "departement_geographique", "ville"]
        widgets = {
            "adresse": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Entrez votre adresse complète (ex: 123 Rue de la Paix, Quartier Centre)",
                }
            ),
            "departement_geographique": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["adresse"].required = True
        self.fields["adresse"].help_text = (
            "Veuillez saisir une adresse détaillée avec au moins le numéro, la rue et le quartier."
        )
        self.fields["departement_geographique"].label = "Département"
        self.fields["departement_geographique"].required = True
        departement = (
            self.data.get("departement_geographique")
            if self.is_bound
            else self.instance.departement_geographique
        ) or ""
        self.fields["ville"].choices = choix_communes(departement)
        self.fields["ville"].required = True
        self.fields["ville"].label = "Municipalité"
        if not departement:
            self.fields["ville"].choices = [("", "Choisissez d’abord un département")]


class EcoleCandidatForm(forms.ModelForm):
    zone = forms.ChoiceField(
        choices=(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    certificat = forms.FileField(
        label="Certificat Scolaire",
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_certificat_scolaire,
        ],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
        ),
    )

    class Meta:
        model = EcoleCandidat
        fields = ["nom", "zone", "certificat"]
        widgets = {
            "nom": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Commencez à taper pour rechercher une école",
                }
            ),
        }

    def __init__(self, *args, ecole_existante=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.ecole_existante = ecole_existante
        self.fields["nom"].label = "Nom de l'École"
        self.fields["nom"].required = not ecole_existante
        self.fields["zone"].label = "Zone (Commune ou municipalité)"
        self.fields["zone"].required = False
        self.fields["zone"].choices = choix_communes()
        if self.instance.zone and self.instance.zone not in dict(
            self.fields["zone"].choices
        ):
            self.fields["zone"].choices += ((self.instance.zone, self.instance.zone),)
        self.fields["certificat"].required = not ecole_existante

    def clean(self):
        donnees = super().clean()
        if donnees.get("nom") and not donnees.get("certificat"):
            self.add_error("certificat", "Le certificat scolaire est obligatoire.")
        return donnees


class ParcoursCandidatForm(forms.ModelForm):
    certificat = forms.FileField(
        required=False,
        label="Certificat d’Étude/Relevé de Notes",
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_document_etude,
        ],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
        ),
    )
    lettre_recommandation = forms.FileField(
        required=False,
        label="Lettre de Recommandation",
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_document_etude,
        ],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
        ),
    )
    lettre_motivation = forms.FileField(
        required=False,
        label="Lettre de Motivation",
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_document_etude,
        ],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
        ),
    )
    cv_ou_autre_document = forms.FileField(
        required=False,
        label="CV / Autre Document",
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]),
            valider_taille_document_etude,
        ],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
        ),
    )

    class Meta:
        model = ParcoursCandidat
        fields = [
            "etablissement",
            "niveau",
            "programme",
            "annee_obtention",
            "type_document",
            "certificat",
            "lettre_recommandation",
            "lettre_motivation",
            "cv_ou_autre_document",
        ]
        widgets = {
            "etablissement": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Commencez à taper pour rechercher un établissement",
                }
            ),
            "niveau": forms.Select(attrs={"class": "form-select"}),
            "programme": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "ex. Sciences Expérimentales",
                }
            ),
            "annee_obtention": forms.NumberInput(
                attrs={"class": "form-control", "min": 1965, "max": date.today().year}
            ),
            "type_document": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "ex. Certificat, Diplôme, Licence",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.required = False

    def clean(self):
        donnees = super().clean()
        if donnees.get("etablissement") and not donnees.get("certificat"):
            self.add_error(
                "certificat",
                "Ajoutez le certificat ou le relevé de notes de cet établissement.",
            )
        annee = donnees.get("annee_obtention")
        if annee and not 1965 <= annee <= date.today().year:
            self.add_error(
                "annee_obtention",
                f"L’année doit être comprise entre 1965 et {date.today().year}.",
            )
        return donnees

    def save(self, commit=True):
        return super().save(commit=commit)
