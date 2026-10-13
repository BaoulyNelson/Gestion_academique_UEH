from decimal import Decimal, InvalidOperation

from django import forms

from .models import Entite, RegleAcademique


class FormulaireRegleAcademique(forms.ModelForm):
    seuil_reussite_cours = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        max_digits=5,
        decimal_places=2,
        label="Note d'obtention du cours (/100)",
        widget=forms.NumberInput(attrs={"min": "0", "max": "100", "step": "0.01"}),
    )
    seuil_reprise_cours = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        max_digits=5,
        decimal_places=2,
        label="Seuil minimal de reprise (/100)",
        widget=forms.NumberInput(attrs={"min": "0", "max": "100", "step": "0.01"}),
    )
    note_eliminatoire = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        max_digits=5,
        decimal_places=2,
        label="Note eliminatoire (/100)",
        widget=forms.NumberInput(attrs={"min": "0", "max": "100", "step": "0.01"}),
    )
    credits_requis = forms.IntegerField(
        required=False,
        min_value=0,
        label="Credits requis",
        widget=forms.NumberInput(attrs={"min": "0", "step": "1"}),
    )
    mentions = forms.JSONField(
        required=False,
        initial=dict,
        label="Mentions et seuils (/100)",
        help_text='Objet JSON, par exemple {"Passable": 60, "Bien": 70}.',
        widget=forms.Textarea(attrs={"rows": 4, "spellcheck": "false"}),
    )

    class Meta:
        model = RegleAcademique
        fields = ("entite", "version", "date_effet", "est_active")
        widgets = {"date_effet": forms.DateInput(attrs={"type": "date"})}

    CLES_PARAMETRES = (
        "seuil_reussite_cours",
        "seuil_reprise_cours",
        "note_eliminatoire",
        "credits_requis",
        "mentions",
    )

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["entite"].queryset = (
            Entite.objects.all()
            if utilisateur.is_superuser
            else Entite.objects.filter(pk=utilisateur.entite_id)
        )
        parametres = self.instance.parametres if self.instance.pk else {}
        for cle in self.CLES_PARAMETRES:
            if cle in parametres:
                self.initial.setdefault(cle, parametres[cle])

    def clean_mentions(self):
        mentions = self.cleaned_data.get("mentions") or {}
        if not isinstance(mentions, dict):
            raise forms.ValidationError("Les mentions doivent etre un objet JSON.")
        for nom, valeur in mentions.items():
            if not isinstance(nom, str) or not nom.strip():
                raise forms.ValidationError("Chaque mention doit avoir un nom.")
            try:
                seuil = Decimal(str(valeur))
            except (InvalidOperation, TypeError, ValueError):
                raise forms.ValidationError(
                    f"Le seuil de la mention {nom} doit etre numerique."
                )
            if not seuil.is_finite() or not Decimal("0") <= seuil <= Decimal("100"):
                raise forms.ValidationError(
                    f"Le seuil de la mention {nom} doit etre entre 0 et 100."
                )
        return mentions

    def clean(self):
        donnees = super().clean()
        obtention = donnees.get("seuil_reussite_cours")
        reprise = donnees.get("seuil_reprise_cours")
        if obtention is not None and reprise is not None and reprise > obtention:
            self.add_error(
                "seuil_reprise_cours",
                "Le seuil de reprise ne peut depasser la note d'obtention.",
            )
        return donnees

    def save(self, commit=True):
        regle = super().save(commit=False)
        parametres = dict(regle.parametres or {})
        for cle in self.CLES_PARAMETRES:
            valeur = self.cleaned_data.get(cle)
            if valeur in (None, "") or valeur == {}:
                parametres.pop(cle, None)
            elif cle in {
                "seuil_reussite_cours",
                "seuil_reprise_cours",
                "note_eliminatoire",
            }:
                parametres[cle] = str(valeur)
            else:
                parametres[cle] = valeur
        regle.parametres = parametres
        if commit:
            regle.save()
        return regle
