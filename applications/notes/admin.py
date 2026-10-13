from django.contrib import admin

from .models import Evaluation, ProgrammationExamen


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("etudiant", "cours", "periode", "libelle", "note", "est_publiee")
    list_filter = ("est_publiee", "cours__programme__entite", "periode")
    search_fields = (
        "etudiant__username",
        "etudiant__last_name",
        "etudiant__first_name",
        "cours__code",
    )
    autocomplete_fields = ("etudiant", "cours", "periode", "saisie_par")


@admin.register(ProgrammationExamen)
class ProgrammationExamenAdmin(admin.ModelAdmin):
    list_display = ("libelle", "cours", "periode", "date_debut", "salle", "statut")
    list_filter = ("statut", "cours__programme__entite", "periode")
    search_fields = ("libelle", "cours__code", "cours__nom", "salle")
    autocomplete_fields = ("cours", "periode", "planifie_par")
