from django.contrib import admin

from .models import (
    AffectationCours,
    Cours,
    Entite,
    PeriodeAcademique,
    Programme,
    RegleAcademique,
)


@admin.register(Entite)
class EntiteAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "regime", "est_active")
    list_filter = ("regime", "est_active")
    search_fields = ("code", "nom")


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "entite", "type_programme", "est_actif")
    list_filter = ("entite", "type_programme", "est_actif")
    search_fields = ("code", "nom", "entite__nom")


@admin.register(Cours)
class CoursAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "nom",
        "programme",
        "credits",
        "est_obligatoire",
        "est_actif",
    )
    list_filter = ("programme__entite", "programme", "est_obligatoire", "est_actif")
    search_fields = ("code", "nom", "programme__nom")


@admin.register(PeriodeAcademique)
class PeriodeAcademiqueAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "nom",
        "entite",
        "annee_academique",
        "type_periode",
        "est_ouverte",
    )
    list_filter = ("entite", "annee_academique", "type_periode", "est_ouverte")
    search_fields = ("code", "nom", "annee_academique")


@admin.register(RegleAcademique)
class RegleAcademiqueAdmin(admin.ModelAdmin):
    list_display = ("entite", "version", "date_effet", "est_active")
    list_filter = ("entite", "est_active")
    search_fields = ("entite__nom", "version")


@admin.register(AffectationCours)
class AffectationCoursAdmin(admin.ModelAdmin):
    list_display = ("professeur", "cours", "periode")
    list_filter = ("periode__entite", "periode", "cours__programme")
    search_fields = (
        "professeur__username",
        "professeur__last_name",
        "cours__code",
        "cours__nom",
    )
    autocomplete_fields = ("professeur", "cours", "periode")
