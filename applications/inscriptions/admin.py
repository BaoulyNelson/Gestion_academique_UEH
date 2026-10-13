from django.contrib import admin

from .models import (
    InscriptionPedagogique,
    PaiementScolarite,
    SelectionCours,
    TarifScolarite,
)


class SelectionCoursInline(admin.TabularInline):
    model = SelectionCours
    extra = 0


@admin.register(InscriptionPedagogique)
class InscriptionPedagogiqueAdmin(admin.ModelAdmin):
    list_display = ("etudiant", "programme", "periode", "statut", "date_creation")
    list_filter = ("statut", "programme__entite", "periode")
    search_fields = (
        "etudiant__username",
        "etudiant__last_name",
        "etudiant__first_name",
        "programme__nom",
    )
    autocomplete_fields = ("etudiant", "programme", "periode")
    inlines = (SelectionCoursInline,)


@admin.register(SelectionCours)
class SelectionCoursAdmin(admin.ModelAdmin):
    list_display = ("inscription", "cours")
    search_fields = ("inscription__etudiant__username", "cours__code", "cours__nom")


@admin.register(TarifScolarite)
class TarifScolariteAdmin(admin.ModelAdmin):
    list_display = ("programme", "periode", "montant", "devise", "est_actif")
    list_filter = ("programme__entite", "periode", "est_actif")
    search_fields = ("programme__code", "programme__nom", "periode__nom")
    autocomplete_fields = ("programme", "periode")


@admin.register(PaiementScolarite)
class PaiementScolariteAdmin(admin.ModelAdmin):
    list_display = (
        "etudiant",
        "tarif",
        "montant",
        "reference",
        "statut",
        "valide_par",
        "date_creation",
    )
    list_filter = ("statut", "tarif__programme__entite", "tarif__periode")
    search_fields = (
        "etudiant__username",
        "etudiant__last_name",
        "etudiant__first_name",
        "reference",
    )
    autocomplete_fields = ("etudiant", "tarif", "valide_par")
    readonly_fields = ("date_creation", "date_validation")
