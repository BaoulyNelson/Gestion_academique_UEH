import re

from django import forms
from django.utils import timezone

from applications.candidatures.models import BrouillonInscription, Inscription
from applications.entites.models import Entite, HoraireEntite, Option


def annee_academique_courante():
    annee = timezone.localdate().year
    return f"{annee}-{annee + 1}"


class ReferencePaiementField(forms.RegexField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("regex", r"^[0-9]+$")
        kwargs.setdefault("max_length", 50)
        kwargs.setdefault("required", False)
        kwargs.setdefault(
            "widget",
            forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "1"}),
        )
        kwargs.setdefault(
            "error_messages", {"invalid": "Saisissez uniquement des chiffres."}
        )
        super().__init__(*args, **kwargs)


class InscriptionForm(forms.ModelForm):
    seq = ReferencePaiementField(label="Seq")
    till = ReferencePaiementField(label="Till")

    class Meta:
        model = Inscription
        fields = [
            "annee_academique",
            "entite",
            "option",
            "horaire",
            "seq",
            "till",
            "date_depot",
            "recu_paiement",
        ]
        widgets = {
            "annee_academique": forms.TextInput(
                attrs={"class": "form-control", "readonly": True}
            ),
            "entite": forms.Select(attrs={"class": "form-select"}),
            "option": forms.Select(attrs={"class": "form-select"}),
            "horaire": forms.Select(attrs={"class": "form-select"}),
            "seq": forms.TextInput(attrs={"class": "form-control"}),
            "till": forms.TextInput(attrs={"class": "form-control"}),
            "date_depot": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "recu_paiement": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf,.jpg,.jpeg,.png,.webp",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["entite"].queryset = Entite.objects.filter(
            active=True, inscription_ouverte=True
        )
        entite_id = (
            self.data.get("entite")
            or getattr(self.instance, "entite_id", None)
            or self.initial.get("entite")
        )
        self.fields["option"].queryset = (
            Option.objects.filter(entite_id=entite_id, active=True)
            if entite_id
            else Option.objects.none()
        )
        self.fields["entite"].label = "Entité"
        self.fields["option"].label = "Option d'entité"
        self.fields["option"].required = self.fields["option"].queryset.exists()
        self.fields["horaire"].label = "Vacation"
        self.fields["horaire"].required = (
            HoraireEntite.objects.filter(entite_id=entite_id, actif=True).exists()
            if entite_id
            else False
        )
        self.fields["seq"].label = "Seq"
        self.fields["till"].label = "Till"
        self.fields["date_depot"].label = "Date de dépôt"
        self.fields["recu_paiement"].label = "Reçu de Paiement"
        self.fields["annee_academique"].required = False
        self.fields["annee_academique"].help_text = "Déterminée automatiquement."
        self.initial["annee_academique"] = annee_academique_courante()

    def clean_annee_academique(self):
        return annee_academique_courante()


class BrouillonInscriptionForm(forms.ModelForm):
    seq = ReferencePaiementField(label="Seq")
    till = ReferencePaiementField(label="Till")

    class Meta:
        model = BrouillonInscription
        fields = [
            "entite",
            "option",
            "annee_academique",
            "horaire",
            "seq",
            "till",
            "date_depot",
            "recu_paiement",
        ]
        widgets = {
            "date_depot": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "recu_paiement": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf,.jpg,.jpeg,.png,.webp",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        entite_id = self.data.get("entite") or self.instance.entite_id
        self.fields["entite"].queryset = Entite.objects.filter(
            active=True, inscription_ouverte=True
        )
        self.fields["option"].queryset = (
            Option.objects.filter(entite_id=entite_id, active=True)
            if entite_id
            else Option.objects.none()
        )
        for champ in self.fields.values():
            champ.required = False
        self.fields["annee_academique"].widget.attrs["readonly"] = True
        self.fields["annee_academique"].help_text = "Déterminée automatiquement."
        self.initial["annee_academique"] = annee_academique_courante()

    def clean(self):
        donnees = super().clean()
        donnees["annee_academique"] = annee_academique_courante()
        entite = donnees.get("entite")
        option = donnees.get("option")
        horaire = donnees.get("horaire", "")

        if option and entite and option.entite_id != entite.pk:
            self.add_error("option", "Cette option ne dépend pas de l’entité choisie.")
        if (
            entite
            and horaire
            and not HoraireEntite.objects.filter(
                entite=entite, code=horaire, actif=True
            ).exists()
        ):
            self.add_error("horaire", "Cet horaire n’est pas proposé par l’entité.")
        return donnees
