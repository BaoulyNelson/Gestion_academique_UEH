from decimal import Decimal

from django import forms

from applications.comptes.models import Utilisateur
from applications.inscriptions.models import InscriptionPedagogique
from applications.referentiels.models import (
    Cours,
    Entite,
    PeriodeAcademique,
    Programme,
)

from .models import ProgrammationExamen


class FormulaireConsultationResultats(forms.Form):
    programme = forms.ModelChoiceField(
        queryset=Programme.objects.none(),
        required=False,
        label="Programme",
    )
    periode_reference = forms.ModelChoiceField(
        queryset=PeriodeAcademique.objects.none(),
        required=False,
        label="Periode de reference",
    )
    etudiant = forms.ModelChoiceField(
        queryset=Utilisateur.objects.none(),
        required=False,
        label="Etudiant",
    )

    def __init__(self, *args, utilisateur, etudiant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.etudiant_fixe = etudiant
        if utilisateur.is_superuser:
            entites = Entite.objects.all()
        else:
            entites = Entite.objects.filter(pk=utilisateur.entite_id)

        periodes = PeriodeAcademique.objects.filter(entite__in=entites)
        programmes = Programme.objects.filter(entite__in=entites)
        if etudiant is not None:
            periodes = periodes.filter(
                inscriptions__etudiant=etudiant,
                inscriptions__statut=InscriptionPedagogique.Statut.VALIDEE,
            )
            programmes = programmes.filter(
                inscriptions__etudiant=etudiant,
                inscriptions__statut=InscriptionPedagogique.Statut.VALIDEE,
            )
            self.fields.pop("etudiant")
        else:
            self.fields["etudiant"].queryset = (
                Utilisateur.objects.filter(
                    role=Utilisateur.Role.ETUDIANT,
                    entite__in=entites,
                    inscriptions_pedagogiques__statut=InscriptionPedagogique.Statut.VALIDEE,
                )
                .distinct()
                .order_by("last_name", "first_name", "username")
            )

        self.fields["programme"].queryset = programmes.distinct().order_by("nom")
        self.fields["periode_reference"].queryset = periodes.distinct()

        programme_id = self.data.get("programme")
        etudiant_id = self.data.get("etudiant") or getattr(etudiant, "pk", None)
        if programme_id:
            periodes = periodes.filter(
                inscriptions__programme_id=programme_id,
                inscriptions__statut=InscriptionPedagogique.Statut.VALIDEE,
            )
            if etudiant_id:
                periodes = periodes.filter(inscriptions__etudiant_id=etudiant_id)
            self.fields["periode_reference"].queryset = periodes.distinct()
        elif etudiant_id:
            self.fields["periode_reference"].queryset = periodes.filter(
                inscriptions__etudiant_id=etudiant_id,
                inscriptions__statut=InscriptionPedagogique.Statut.VALIDEE,
            ).distinct()

    def clean(self):
        donnees = super().clean()
        programme = donnees.get("programme")
        periode = donnees.get("periode_reference")
        etudiant = donnees.get("etudiant") or self.etudiant_fixe
        if (
            self.etudiant_fixe is None
            and (programme or etudiant or periode)
            and not (programme or etudiant)
        ):
            raise forms.ValidationError(
                "Choisissez un programme, un etudiant, ou les deux."
            )
        if self.etudiant_fixe is None and (programme or etudiant) and not periode:
            raise forms.ValidationError(
                "Choisissez une periode de reference pour consulter les resultats precedents."
            )
        if (
            programme
            and periode
            and not programme.inscriptions.filter(
                periode=periode,
                statut=InscriptionPedagogique.Statut.VALIDEE,
                **({"etudiant": etudiant} if etudiant else {}),
            ).exists()
        ):
            raise forms.ValidationError(
                "L'etudiant doit etre inscrit au programme pour cette periode de reference."
            )
        if (
            etudiant
            and periode
            and not programme
            and not etudiant.inscriptions_pedagogiques.filter(
                periode=periode,
                statut=InscriptionPedagogique.Statut.VALIDEE,
            ).exists()
        ):
            raise forms.ValidationError(
                "L'etudiant doit etre inscrit pour cette periode de reference."
            )
        return donnees


class FormulaireListeEvaluations(forms.Form):
    entite = forms.ModelChoiceField(
        queryset=Entite.objects.none(), required=False, label="Entite"
    )
    programme = forms.ModelChoiceField(
        queryset=Programme.objects.none(), required=False, label="Programme"
    )
    periode = forms.ModelChoiceField(
        queryset=PeriodeAcademique.objects.none(), required=False, label="Periode"
    )
    cours = forms.ModelMultipleChoiceField(
        queryset=Cours.objects.none(),
        required=False,
        label="Cours",
        widget=forms.SelectMultiple(attrs={"size": "5"}),
    )

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        self.entite_fixe = None
        if utilisateur.is_superuser:
            entites = Entite.objects.all()
        else:
            self.entite_fixe = Entite.objects.filter(pk=utilisateur.entite_id).first()
            entites = Entite.objects.filter(pk=utilisateur.entite_id)
            self.fields["entite"].initial = utilisateur.entite_id
            self.fields["entite"].widget = forms.HiddenInput()

        self.fields["entite"].queryset = entites
        entite_id = self.data.get("entite") or utilisateur.entite_id
        programmes = Programme.objects.filter(entite_id=entite_id)
        periodes = PeriodeAcademique.objects.filter(entite_id=entite_id)
        programme_id = self.data.get("programme")
        if programme_id:
            programmes = programmes.filter(pk=programme_id)
        self.fields["programme"].queryset = programmes.distinct()
        self.fields["periode"].queryset = periodes.distinct()

        cours = Cours.objects.filter(programme__entite_id=entite_id)
        if programme_id:
            cours = cours.filter(programme_id=programme_id)
        self.fields["cours"].queryset = cours.distinct().order_by(
            "programme__nom", "code"
        )

    def clean(self):
        donnees = super().clean()
        entite = donnees.get("entite") or self.entite_fixe
        programme = donnees.get("programme")
        periode = donnees.get("periode")
        cours = donnees.get("cours")
        if not any((programme, periode, cours)):
            return donnees
        if not programme or not periode:
            raise forms.ValidationError(
                "Choisissez un programme et une periode pour afficher les notes."
            )
        if entite and programme.entite_id != entite.pk:
            raise forms.ValidationError(
                "Le programme ne correspond pas a cette entite."
            )
        if entite and periode.entite_id != entite.pk:
            raise forms.ValidationError("La periode ne correspond pas a cette entite.")
        if programme.entite_id != periode.entite_id:
            raise forms.ValidationError(
                "Le programme et la periode doivent appartenir a la meme entite."
            )
        if any(cours_item.programme_id != programme.pk for cours_item in cours):
            raise forms.ValidationError(
                "Tous les cours doivent appartenir au programme choisi."
            )
        return donnees


class FormulaireProgrammationExamen(forms.ModelForm):
    class Meta:
        model = ProgrammationExamen
        fields = (
            "cours",
            "periode",
            "libelle",
            "date_debut",
            "date_fin",
            "salle",
            "consignes",
            "statut",
        )
        widgets = {
            "date_debut": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "date_fin": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "consignes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        if utilisateur.is_superuser:
            entites = Entite.objects.all()
        else:
            entites = Entite.objects.filter(pk=utilisateur.entite_id)
        self.fields["cours"].queryset = Cours.objects.filter(
            programme__entite__in=entites
        ).select_related("programme")
        self.fields["periode"].queryset = PeriodeAcademique.objects.filter(
            entite__in=entites
        )
        for nom in ("date_debut", "date_fin"):
            self.fields[nom].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean(self):
        donnees = super().clean()
        cours = donnees.get("cours")
        periode = donnees.get("periode")
        if cours and periode and cours.programme.entite_id != periode.entite_id:
            self.add_error("periode", "La periode doit appartenir a l'entite du cours.")
        return donnees


class FormulaireEvaluation(forms.Form):
    etudiant = forms.ModelChoiceField(
        queryset=Utilisateur.objects.none(),
        label="Etudiant inscrit",
    )
    libelle = forms.CharField(
        max_length=120,
        label="Evaluation",
        help_text="Examen final, travail pratique, devoir...",
    )
    note = forms.DecimalField(
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        max_digits=5,
        decimal_places=2,
        label="Note sur 100",
        widget=forms.NumberInput(attrs={"min": "0", "max": "100", "step": "0.01"}),
    )
    coefficient = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=5,
        decimal_places=2,
        initial=Decimal("1.00"),
        label="Coefficient",
        widget=forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
    )

    def __init__(self, *args, cours, periode, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["etudiant"].queryset = (
            Utilisateur.objects.filter(
                role=Utilisateur.Role.ETUDIANT,
                inscriptions_pedagogiques__programme_id=cours.programme_id,
                inscriptions_pedagogiques__periode=periode,
                inscriptions_pedagogiques__statut=InscriptionPedagogique.Statut.VALIDEE,
                inscriptions_pedagogiques__conditions_passage_verifiees=True,
                inscriptions_pedagogiques__cours_selectionnes__cours=cours,
            )
            .distinct()
            .order_by("last_name", "first_name", "username")
        )


class FormulaireImportEvaluations(forms.Form):
    fichier = forms.FileField(
        label="Fichier Excel (.xlsx)",
        widget=forms.FileInput(attrs={"accept": ".xlsx"}),
    )

    def clean_fichier(self):
        fichier = self.cleaned_data["fichier"]
        if not fichier.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Le fichier doit etre au format .xlsx.")
        if fichier.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Le fichier ne peut pas depasser 5 Mo.")
        return fichier
