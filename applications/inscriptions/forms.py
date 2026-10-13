from django import forms

from applications.comptes.models import Utilisateur
from applications.inscriptions.models import PaiementScolarite, TarifScolarite
from applications.referentiels.models import (
    Cours,
    PeriodeAcademique,
    Programme,
)


class ChoixTarifField(forms.ModelChoiceField):
    def label_from_instance(self, tarif):
        return f"{tarif.programme.nom} - {tarif.periode.nom} ({tarif.montant} {tarif.devise})"


class FormulairePaiementScolarite(forms.ModelForm):
    tarif = ChoixTarifField(
        queryset=TarifScolarite.objects.none(),
        label="Programme et periode",
    )

    class Meta:
        model = PaiementScolarite
        fields = ("tarif", "montant", "reference", "date_paiement")
        widgets = {
            "montant": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "date_paiement": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        tarifs = TarifScolarite.objects.filter(
            est_actif=True,
            periode__est_ouverte=True,
        ).select_related("programme", "periode")
        if utilisateur.entite_id:
            tarifs = tarifs.filter(programme__entite_id=utilisateur.entite_id)
        else:
            tarifs = tarifs.none()
        self.fields["tarif"].queryset = tarifs


class FormulaireInscriptionPedagogique(forms.Form):
    periode = forms.ModelChoiceField(
        queryset=PeriodeAcademique.objects.none(),
        label="Periode academique",
    )
    programme = forms.ModelChoiceField(
        queryset=Programme.objects.none(),
        label="Programme",
    )

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        periodes = PeriodeAcademique.objects.filter(
            entite_id=utilisateur.entite_id,
            est_ouverte=True,
            tarifs_scolarite__est_actif=True,
        ).distinct()
        self.fields["periode"].queryset = periodes

        periode_id = self.data.get("periode") or self.initial.get("periode")
        programmes = Programme.objects.filter(
            entite_id=utilisateur.entite_id,
            est_actif=True,
            tarifs_scolarite__est_actif=True,
            tarifs_scolarite__periode__est_ouverte=True,
        )
        if periode_id:
            programmes = programmes.filter(tarifs_scolarite__periode_id=periode_id)
        self.fields["programme"].queryset = programmes.distinct()

    def clean(self):
        donnees = super().clean()
        periode = donnees.get("periode")
        programme = donnees.get("programme")
        if periode and programme:
            if periode.entite_id != programme.entite_id:
                raise forms.ValidationError(
                    "La periode et le programme doivent appartenir a la meme entite."
                )
            tarif_disponible = TarifScolarite.objects.filter(
                programme=programme,
                periode=periode,
                est_actif=True,
            ).exists()
            if not tarif_disponible:
                raise forms.ValidationError(
                    "Aucun tarif actif n'est configure pour ce programme et cette periode."
                )
        return donnees


class ChoixCoursField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, cours):
        type_cours = "Obligatoire" if cours.est_obligatoire else "Optionnel"
        return f"{type_cours} · {cours.code} · {cours.nom} ({cours.credits} credits)"


class FormulaireSelectionCours(forms.Form):
    cours = ChoixCoursField(
        queryset=Cours.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Cours pour cette periode",
    )

    def __init__(self, *args, inscription, **kwargs):
        super().__init__(*args, **kwargs)
        cours_offerts = Cours.objects.filter(
            programme=inscription.programme,
            est_actif=True,
            affectations_professeurs__periode=inscription.periode,
        ).distinct()
        self.fields["cours"].queryset = cours_offerts
        if not args or args[0] is None:
            self.initial["cours"] = inscription.cours_selectionnes.values_list(
                "cours_id", flat=True
            )

    def clean_cours(self):
        cours_choisis = self.cleaned_data["cours"]
        codes_choisis = {cours.pk for cours in cours_choisis}
        cours_obligatoires = set(
            self.fields["cours"]
            .queryset.filter(est_obligatoire=True)
            .values_list("pk", flat=True)
        )
        manquants = cours_obligatoires - codes_choisis
        if manquants:
            raise forms.ValidationError(
                "Tous les cours obligatoires offerts doivent etre selectionnes."
            )
        if not codes_choisis:
            raise forms.ValidationError("Choisissez au moins un cours.")
        return cours_choisis


class FormulaireRechercheDossier(forms.Form):
    identifiant = forms.CharField(
        label="Code etudiant, NIF ou CIN",
        max_length=48,
        strip=True,
    )
    periode = forms.ModelChoiceField(
        queryset=PeriodeAcademique.objects.none(),
        label="Periode academique",
    )

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        if utilisateur.is_superuser:
            periodes = PeriodeAcademique.objects.all()
        elif utilisateur.role == Utilisateur.Role.PERSONNEL and utilisateur.entite_id:
            periodes = PeriodeAcademique.objects.filter(entite_id=utilisateur.entite_id)
        else:
            periodes = PeriodeAcademique.objects.none()
        self.fields["periode"].queryset = periodes
