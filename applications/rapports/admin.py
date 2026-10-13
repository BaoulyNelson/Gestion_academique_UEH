from django.contrib import admin

from .models import ActeAcademique, DossierEtudes, SoutenanceMemoire


@admin.register(DossierEtudes)
class DossierEtudesAdmin(admin.ModelAdmin):
    list_display = ("etudiant", "programme", "statut", "date_ouverture", "date_cloture")
    list_filter = ("statut", "programme__entite", "programme")
    search_fields = (
        "etudiant__username",
        "etudiant__last_name",
        "etudiant__first_name",
        "programme__code",
        "programme__nom",
    )
    autocomplete_fields = ("etudiant", "programme", "cree_par")


@admin.register(ActeAcademique)
class ActeAcademiqueAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "type_acte",
        "etudiant",
        "programme",
        "periode",
        "date_delivrance",
        "est_annule",
    )
    list_filter = ("type_acte", "est_annule", "programme__entite", "periode")
    search_fields = (
        "reference",
        "etudiant__username",
        "etudiant__last_name",
        "etudiant__first_name",
    )
    autocomplete_fields = ("etudiant", "programme", "periode", "delivre_par")


@admin.register(SoutenanceMemoire)
class SoutenanceMemoireAdmin(admin.ModelAdmin):
    list_display = (
        "etudiant",
        "programme",
        "titre",
        "date_soutenance",
        "statut",
        "note",
    )
    list_filter = ("statut", "programme__entite", "periode")
    search_fields = (
        "etudiant__username",
        "etudiant__last_name",
        "etudiant__first_name",
        "titre",
    )
    autocomplete_fields = ("etudiant", "programme", "periode", "enregistre_par")
