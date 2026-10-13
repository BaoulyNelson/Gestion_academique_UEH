from django import forms
from django.contrib import admin

from applications.candidats.models import Candidat, EcoleCandidat, ParcoursCandidat
from applications.comptes.models import Utilisateur
from applications.documents.models import DocumentCandidat
from applications.entites.models import entites_autorisees


class CandidatDossierAdminForm(forms.ModelForm):
    prenom = forms.CharField(label="Prénom", max_length=100, required=False)
    nom = forms.CharField(label="Nom", max_length=100, required=False)
    email = forms.EmailField(
        label="Adresse e-mail du compte",
        required=False,
        disabled=True,
        help_text="L’adresse de connexion n’est pas modifiable depuis le dossier.",
    )

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
        widgets = {
            "date_naissance": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["prenom"].initial = self.instance.utilisateur.prenom
            self.fields["nom"].initial = self.instance.utilisateur.nom
            self.fields["email"].initial = self.instance.utilisateur.email


class EcoleCandidatInline(admin.TabularInline):
    model = EcoleCandidat
    extra = 0
    fields = ("nom", "zone", "certificat", "date_ajout")
    readonly_fields = ("date_ajout",)


class ParcoursCandidatInline(admin.TabularInline):
    model = ParcoursCandidat
    extra = 0
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
        "date_ajout",
    )
    readonly_fields = ("date_ajout",)


class DocumentCandidatInline(admin.TabularInline):
    model = DocumentCandidat
    extra = 0
    fields = ("type_document", "fichier", "date_televersement")
    readonly_fields = ("date_televersement",)


@admin.register(Candidat)
class CandidatAdmin(admin.ModelAdmin):
    form = CandidatDossierAdminForm
    list_display = ("candidat", "courriel", "telephone", "etablissement_scolaire")
    search_fields = (
        "utilisateur__prenom",
        "utilisateur__nom",
        "utilisateur__email",
        "telephone",
    )
    readonly_fields = ("date_creation",)
    inlines = (EcoleCandidatInline, ParcoursCandidatInline, DocumentCandidatInline)
    fieldsets = (
        (
            "Compte candidat",
            {"fields": ("prenom", "nom", "email")},
        ),
        (
            "Identité",
            {
                "fields": (
                    "nationalite",
                    "date_naissance",
                    "lieu_naissance",
                    "sexe",
                    "nom_parent_responsable",
                    "nif",
                    "ninu",
                )
            },
        ),
        (
            "Coordonnées",
            {
                "fields": (
                    "telephone",
                    "adresse",
                    "departement_geographique",
                    "ville",
                )
            },
        ),
        (
            "Scolarité",
            {"fields": ("etablissement_scolaire", "annee_obtention")},
        ),
        ("Historique", {"fields": ("date_creation",)}),
    )

    def get_queryset(self, request):
        queryset = (
            super()
            .get_queryset(request)
            .select_related("utilisateur")
            .filter(
                utilisateur__is_superuser=False,
                utilisateur__administration_entite__isnull=True,
            )
        )
        autorisees = entites_autorisees(request.user)
        if autorisees is None:
            return queryset
        return queryset.filter(inscriptions__entite__in=autorisees).distinct()

    def has_module_permission(self, request):
        autorisees = entites_autorisees(request.user)
        return request.user.is_superuser or bool(
            autorisees is not None and autorisees.exists()
        )

    def has_view_permission(self, request, obj=None):
        return self._autorise(request.user, obj)

    def has_change_permission(self, request, obj=None):
        return self._autorise(request.user, obj)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)

    @staticmethod
    def _autorise(utilisateur, objet=None):
        if utilisateur.is_superuser:
            return True
        autorisees = entites_autorisees(utilisateur)
        if autorisees is None or not autorisees.exists():
            return False
        return (
            objet is None or objet.inscriptions.filter(entite__in=autorisees).exists()
        )

    @admin.display(description="Candidat")
    def candidat(self, obj):
        return obj.utilisateur.get_full_name() or obj.utilisateur.email

    @admin.display(description="E-mail")
    def courriel(self, obj):
        return obj.utilisateur.email

    def save_model(self, request, obj, form, change):
        obj.utilisateur.prenom = form.cleaned_data["prenom"]
        obj.utilisateur.nom = form.cleaned_data["nom"]
        obj.utilisateur.save(update_fields=["prenom", "nom"])
        super().save_model(request, obj, form, change)
