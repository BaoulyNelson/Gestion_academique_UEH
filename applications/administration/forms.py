from django import forms
from django.forms import inlineformset_factory

from applications.candidats.models import Candidat, EcoleCandidat, ParcoursCandidat
from applications.documents.models import DocumentCandidat
from applications.entites.models import (
    Entite,
    HoraireEntite,
    Option,
    Salle,
    entites_autorisees,
)
from applications.resultats.models import EpreuveResultat, Resultat


class ChampsBootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            widget = champ.widget
            if isinstance(widget, forms.HiddenInput):
                continue
            if isinstance(widget, forms.CheckboxInput):
                classe = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                classe = "form-select"
            else:
                classe = "form-control"
            classes_existantes = widget.attrs.get("class", "").split()
            if classe not in classes_existantes:
                classes_existantes.append(classe)
            widget.attrs["class"] = " ".join(classes_existantes)


class AffectationSalleForm(forms.Form):
    salle = forms.ModelChoiceField(
        label="Salle",
        queryset=Salle.objects.none(),
        required=False,
        empty_label="En attente d’affectation",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, entite, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["salle"].queryset = Salle.objects.filter(entite=entite)


class FormulaireRessourceEntite(ChampsBootstrapMixin, forms.ModelForm):
    def __init__(self, *args, utilisateur, **kwargs):
        super().__init__(*args, **kwargs)
        autorisees = entites_autorisees(utilisateur)
        if autorisees is None:
            self.fields["entite"].queryset = Entite.objects.order_by("code")
        else:
            self.fields["entite"].queryset = autorisees
            self.fields["entite"].initial = autorisees.first()
            self.fields["entite"].widget = forms.HiddenInput()


class FormulaireSalle(FormulaireRessourceEntite):
    class Meta:
        model = Salle
        fields = ("entite", "nom", "capacite")


class FormulaireOption(FormulaireRessourceEntite):
    class Meta:
        model = Option
        fields = ("entite", "nom", "active")


class FormulaireHoraire(FormulaireRessourceEntite):
    class Meta:
        model = HoraireEntite
        fields = ("entite", "code", "actif")


class FormulaireDossierCandidat(ChampsBootstrapMixin, forms.ModelForm):
    prenom = forms.CharField(label="Prénom", max_length=100, required=False)
    nom = forms.CharField(label="Nom", max_length=100, required=False)
    email = forms.EmailField(label="Adresse e-mail", disabled=True, required=False)

    class Meta:
        model = Candidat
        fields = (
            "prenom",
            "nom",
            "email",
            "nationalite",
            "telephone",
            "date_naissance",
            "lieu_naissance",
            "sexe",
            "nom_parent_responsable",
            "nif",
            "ninu",
            "adresse",
            "departement_geographique",
            "ville",
            "etablissement_scolaire",
            "annee_obtention",
        )
        widgets = {"date_naissance": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["prenom"].initial = self.instance.utilisateur.prenom
            self.fields["nom"].initial = self.instance.utilisateur.nom
            self.fields["email"].initial = self.instance.utilisateur.email

    def save(self, commit=True):
        candidat = super().save(commit=False)
        candidat.utilisateur.prenom = self.cleaned_data["prenom"]
        candidat.utilisateur.nom = self.cleaned_data["nom"]
        if commit:
            candidat.utilisateur.save(update_fields=["prenom", "nom"])
            candidat.save()
            self.save_m2m()
        return candidat


class FormulaireEcoleCandidat(ChampsBootstrapMixin, forms.ModelForm):
    class Meta:
        model = EcoleCandidat
        fields = ("nom", "zone", "certificat")


class FormulaireParcoursCandidat(ChampsBootstrapMixin, forms.ModelForm):
    class Meta:
        model = ParcoursCandidat
        fields = (
            "etablissement",
            "niveau",
            "programme",
            "annee_obtention",
            "type_document",
            "certificat",
            "lettre_recommandation",
            "lettre_motivation",
            "cv_ou_autre_document",
        )


class FormulaireDocumentCandidat(ChampsBootstrapMixin, forms.ModelForm):
    class Meta:
        model = DocumentCandidat
        fields = ("type_document", "fichier")


EcolesCandidatFormSet = inlineformset_factory(
    Candidat,
    EcoleCandidat,
    form=FormulaireEcoleCandidat,
    extra=1,
    can_delete=True,
)
ParcoursCandidatFormSet = inlineformset_factory(
    Candidat,
    ParcoursCandidat,
    form=FormulaireParcoursCandidat,
    extra=1,
    can_delete=True,
)
DocumentsCandidatFormSet = inlineformset_factory(
    Candidat,
    DocumentCandidat,
    form=FormulaireDocumentCandidat,
    extra=1,
    can_delete=True,
)


class FormulaireResultat(ChampsBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Resultat
        fields = ("publie",)


class FormulaireEpreuveResultat(ChampsBootstrapMixin, forms.ModelForm):
    class Meta:
        model = EpreuveResultat
        fields = ("nom", "note", "bareme", "coefficient", "ordre")


EpreuvesResultatFormSet = inlineformset_factory(
    Resultat,
    EpreuveResultat,
    form=FormulaireEpreuveResultat,
    extra=1,
    can_delete=True,
)
