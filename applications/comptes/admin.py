from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from allauth.account.models import EmailAddress

from .models import ProfilEtudiant, SiteConfiguration, Utilisateur


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ("nom_site", "slogan", "telephone", "email_contact")
    fieldsets = (
        ("Identite du site", {"fields": ("nom_site", "slogan", "logo")}),
        ("Coordonnees", {"fields": ("telephone", "email_contact", "adresse")}),
        ("Pied de page", {"fields": ("texte_pied_page",)}),
    )


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "entite",
        "photo_profil",
        "is_active",
    )
    list_filter = ("role", "entite", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = UserAdmin.fieldsets + (
        ("Acces GP7", {"fields": ("role", "entite", "photo_profil")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Acces GP7", {"fields": ("email", "role", "entite", "photo_profil")}),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            EmailAddress.objects.update_or_create(
                user=obj,
                email=obj.email,
                defaults={"primary": True, "verified": True},
            )


@admin.register(ProfilEtudiant)
class ProfilEtudiantAdmin(admin.ModelAdmin):
    list_display = ("code_etudiant", "utilisateur", "sexe", "date_naissance")
    list_filter = ("sexe", "utilisateur__entite")
    search_fields = (
        "code_etudiant",
        "nif",
        "cin",
        "utilisateur__username",
        "utilisateur__first_name",
        "utilisateur__last_name",
    )
    autocomplete_fields = ("utilisateur",)
