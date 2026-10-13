from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from .models import SiteConfiguration, Utilisateur


def valider_taille_photo_profil(fichier):
    if fichier.size > 1024 * 1024:
        raise ValidationError("La taille maximale de la photo est de 1 Mo.")


class FormulaireConfigurationSite(forms.ModelForm):
    class Meta:
        model = SiteConfiguration
        fields = (
            "nom_site",
            "slogan",
            "logo",
            "telephone",
            "email_contact",
            "adresse",
            "texte_pied_page",
        )
        widgets = {
            "logo": forms.FileInput(attrs={"accept": "image/*"}),
            "texte_pied_page": forms.Textarea(attrs={"rows": 4}),
        }


class FormulaireProfilAdministrateur(forms.Form):
    prenom = forms.CharField(
        label="Prénom",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    nom = forms.CharField(
        label="Nom",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    photo_profil = forms.FileField(
        label="Photo de profil",
        required=False,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp"]),
            valider_taille_photo_profil,
        ],
        widget=forms.FileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "data-apercu-photo-profil": "",
            }
        ),
    )

    def __init__(self, *args, instance, **kwargs):
        self.instance = instance
        initial = kwargs.pop("initial", {})
        initial.setdefault("prenom", instance.first_name)
        initial.setdefault("nom", instance.last_name)
        super().__init__(*args, initial=initial, **kwargs)
        for champ in self.fields.values():
            champ.widget.attrs["class"] = "form-control"

    def save(self):
        self.instance.first_name = self.cleaned_data["prenom"].strip()
        self.instance.last_name = self.cleaned_data["nom"].strip()
        photo = self.cleaned_data.get("photo_profil")
        if photo:
            self.instance.photo_profil = photo
        self.instance.save(update_fields=["first_name", "last_name", "photo_profil"])
        return self.instance


class FormulaireInscription(forms.Form):
    field_order = ["email", "prenom", "nom", "password1", "password2"]

    prenom = forms.CharField(
        label="Prénom",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    nom = forms.CharField(
        label="Nom",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )

    def signup(self, request, user):
        user.first_name = self.cleaned_data["prenom"].strip()
        user.last_name = self.cleaned_data["nom"].strip()
        user.save(update_fields=["first_name", "last_name"])
