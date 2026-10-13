from django import forms

from applications.comptes.models import Utilisateur
from applications.inscriptions.models import InscriptionPedagogique
from applications.rapports.models import (
    ActeAcademique,
    DossierEtudes,
    SoutenanceMemoire,
)
from applications.referentiels.models import (
    Cours,
    Entite,
    PeriodeAcademique,
    Programme,
)


class FiltresRapport(forms.Form):
    entite = forms.ModelChoiceField(
        queryset=Entite.objects.none(),
        required=False,
        label="Entite",
    )
    periode = forms.ModelChoiceField(
        queryset=PeriodeAcademique.objects.none(),
        required=False,
        label="Periode academique",
    )
    programme = forms.ModelChoiceField(
        queryset=Programme.objects.none(),
        required=False,
        label="Programme",
    )

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        if utilisateur.is_superuser:
            entites = Entite.objects.all()
        else:
            entites = Entite.objects.filter(pk=utilisateur.entite_id)
            self.fields["entite"].initial = utilisateur.entite_id
            self.fields["entite"].widget = forms.HiddenInput()

        self.fields["entite"].queryset = entites
        entite_id = (
            self.data.get("entite")
            or self.initial.get("entite")
            or utilisateur.entite_id
        )
        periodes = PeriodeAcademique.objects.filter(entite_id=entite_id)
        programmes = Programme.objects.filter(entite_id=entite_id)
        periode_id = self.data.get("periode") or self.initial.get("periode")
        if periode_id:
            programmes = programmes.filter(
                tarifs_scolarite__periode_id=periode_id
            ) | programmes.filter(inscriptions__periode_id=periode_id)
        self.fields["periode"].queryset = periodes.distinct()
        self.fields["programme"].queryset = programmes.distinct()

    def clean(self):
        donnees = super().clean()
        entite = donnees.get("entite")
        periode = donnees.get("periode")
        programme = donnees.get("programme")
        if periode and entite and periode.entite_id != entite.pk:
            raise forms.ValidationError("La periode ne correspond pas a cette entite.")
        if programme and entite and programme.entite_id != entite.pk:
            raise forms.ValidationError(
                "Le programme ne correspond pas a cette entite."
            )
        if (
            periode
            and programme
            and not (
                programme.tarifs_scolarite.filter(periode=periode).exists()
                or programme.inscriptions.filter(periode=periode).exists()
            )
        ):
            raise forms.ValidationError(
                "Le programme ne correspond pas a cette periode."
            )
        return donnees


class FormulaireEmissionActe(forms.ModelForm):
    class Meta:
        model = ActeAcademique
        fields = (
            "etudiant",
            "programme",
            "periode",
            "type_acte",
            "reference",
            "date_delivrance",
        )
        widgets = {
            "date_delivrance": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        if utilisateur.is_superuser:
            entites = Entite.objects.all()
        else:
            entites = Entite.objects.filter(pk=utilisateur.entite_id)

        self.fields["etudiant"].queryset = Utilisateur.objects.filter(
            role=Utilisateur.Role.ETUDIANT,
            entite__in=entites,
        ).order_by("last_name", "first_name", "username")
        self.fields["programme"].queryset = Programme.objects.filter(entite__in=entites)
        self.fields["periode"].queryset = PeriodeAcademique.objects.filter(
            entite__in=entites
        )
        self.fields["reference"].help_text = (
            "Reference unique attribuee par le Registrariat."
        )

    def clean(self):
        donnees = super().clean()
        etudiant = donnees.get("etudiant")
        programme = donnees.get("programme")
        periode = donnees.get("periode")
        if etudiant and programme and etudiant.entite_id != programme.entite_id:
            self.add_error("etudiant", "L'etudiant doit appartenir a cette entite.")
        if programme and periode and programme.entite_id != periode.entite_id:
            self.add_error("periode", "La periode doit appartenir a cette entite.")
        return donnees


class FormulaireSoutenance(forms.ModelForm):
    class Meta:
        model = SoutenanceMemoire
        fields = (
            "etudiant",
            "programme",
            "periode",
            "titre",
            "date_soutenance",
            "statut",
            "note",
            "jury",
        )
        widgets = {
            "date_soutenance": forms.DateInput(attrs={"type": "date"}),
            "note": forms.NumberInput(attrs={"min": "0", "max": "100", "step": "0.01"}),
        }

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        if utilisateur.is_superuser:
            entites = Entite.objects.all()
        else:
            entites = Entite.objects.filter(pk=utilisateur.entite_id)
        self.fields["etudiant"].queryset = Utilisateur.objects.filter(
            role=Utilisateur.Role.ETUDIANT,
            entite__in=entites,
        ).order_by("last_name", "first_name", "username")
        self.fields["programme"].queryset = Programme.objects.filter(entite__in=entites)
        self.fields["periode"].queryset = PeriodeAcademique.objects.filter(
            entite__in=entites
        )
        self.fields["note"].required = False
        self.fields["jury"].widget = forms.Textarea(attrs={"rows": 3})

    def clean(self):
        donnees = super().clean()
        etudiant = donnees.get("etudiant")
        programme = donnees.get("programme")
        periode = donnees.get("periode")
        if etudiant and programme and etudiant.entite_id != programme.entite_id:
            self.add_error("etudiant", "L'etudiant doit appartenir a cette entite.")
        if programme and periode and programme.entite_id != periode.entite_id:
            self.add_error("periode", "La periode doit appartenir a cette entite.")
        return donnees


class FormulaireDossierEtudes(forms.ModelForm):
    class Meta:
        model = DossierEtudes
        fields = (
            "etudiant",
            "programme",
            "statut",
            "date_ouverture",
            "date_cloture",
            "motif_cloture",
        )
        widgets = {
            "date_ouverture": forms.DateInput(attrs={"type": "date"}),
            "date_cloture": forms.DateInput(attrs={"type": "date"}),
            "motif_cloture": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        if utilisateur.is_superuser:
            entites = Entite.objects.all()
        else:
            entites = Entite.objects.filter(pk=utilisateur.entite_id)
        self.fields["etudiant"].queryset = Utilisateur.objects.filter(
            role=Utilisateur.Role.ETUDIANT,
            entite__in=entites,
        ).order_by("last_name", "first_name", "username")
        self.fields["programme"].queryset = Programme.objects.filter(entite__in=entites)
        self.fields["date_cloture"].required = False
        self.fields["motif_cloture"].required = False

    def clean(self):
        donnees = super().clean()
        etudiant = donnees.get("etudiant")
        programme = donnees.get("programme")
        statut = donnees.get("statut")
        if etudiant and programme and etudiant.entite_id != programme.entite_id:
            self.add_error("etudiant", "L'etudiant doit appartenir a cette entite.")
        if statut == DossierEtudes.Statut.EN_COURS:
            donnees["date_cloture"] = None
            donnees["motif_cloture"] = ""
        return donnees


class FiltresListeEtudiants(FiltresRapport):
    niveau = forms.ModelChoiceField(
        queryset=PeriodeAcademique.objects.none(),
        required=False,
        label="Niveau d'etude",
    )
    cours = forms.ModelChoiceField(
        queryset=Cours.objects.none(), required=False, label="Cours"
    )
    statut = forms.ChoiceField(
        choices=(
            ("", "Tous les statuts"),
            *InscriptionPedagogique.Statut.choices,
        ),
        required=False,
        label="Statut d'inscription",
    )
    statut_dossier = forms.ChoiceField(
        choices=(
            ("", "Tous les statuts de dossier"),
            *DossierEtudes.Statut.choices,
        ),
        required=False,
        label="Statut du dossier",
    )
    statut_passage = forms.ChoiceField(
        choices=(
            ("", "Tous les resultats de passage"),
            ("reussite", "Reussite"),
            ("reprise", "A reprendre"),
            ("echec", "Echec"),
            ("en_attente", "En attente de notes ou de regle"),
            ("frais_non_acquittes", "Frais non acquittes"),
        ),
        required=False,
        label="Resultat des conditions de passage",
    )

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, utilisateur=utilisateur, **kwargs)
        entite_id = (
            self.data.get("entite")
            or self.initial.get("entite")
            or utilisateur.entite_id
        )
        cours = Cours.objects.filter(programme__entite_id=entite_id)
        programme_id = self.data.get("programme") or self.initial.get("programme")
        if programme_id:
            cours = cours.filter(programme_id=programme_id)
        self.fields["cours"].queryset = cours
        self.fields["niveau"].queryset = PeriodeAcademique.objects.filter(
            entite_id=entite_id,
            type_periode=PeriodeAcademique.TypePeriode.NIVEAU,
        )

    def clean(self):
        donnees = super().clean()
        cours = donnees.get("cours")
        niveau = donnees.get("niveau")
        programme = donnees.get("programme")
        if cours and programme and cours.programme_id != programme.pk:
            self.add_error("cours", "Le cours ne correspond pas a ce programme.")
        if niveau and donnees.get("periode") and niveau.pk != donnees["periode"].pk:
            self.add_error(
                "niveau",
                "Choisissez un niveau ou une periode, mais pas les deux a la fois.",
            )
        if (
            niveau
            and programme
            and not programme.inscriptions.filter(periode=niveau).exists()
        ):
            self.add_error(
                "niveau", "Ce niveau ne contient pas d'inscription pour ce programme."
            )
        return donnees
