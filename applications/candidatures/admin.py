from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.db import transaction
from django.http import Http404
from allauth.account.models import EmailAddress

from applications.administration.models import JournalAction
from applications.candidatures.models import Inscription
from applications.entites.models import (
    AdministrateurEntite,
    Entite,
    HoraireEntite,
    Option,
    Salle,
    entites_autorisees,
)


class FiltreEntiteAutorisee(SimpleListFilter):
    title = "entité"
    parameter_name = "entite"

    def lookups(self, request, model_admin):
        autorisees = entites_autorisees(request.user)
        entites = Entite.objects.all() if autorisees is None else autorisees
        return [(entite.pk, str(entite)) for entite in entites.order_by("code")]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(entite_id=self.value())
        return queryset


@admin.register(Inscription)
class InscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "numero_dossier",
        "candidat",
        "entite",
        "annee_academique",
        "statut",
        "date_inscription",
    )
    list_filter = (FiltreEntiteAutorisee, "statut", "annee_academique")
    search_fields = (
        "numero_dossier",
        "candidat__utilisateur__email",
        "candidat__utilisateur__nom",
    )
    ordering = ("-date_inscription",)
    autocomplete_fields = ("candidat",)
    readonly_fields = (
        "numero_dossier",
        "rang",
        "candidat",
        "date_inscription",
    )
    actions = ("delete_selected", "valider_inscriptions", "rejeter_inscriptions")

    class Media:
        js = ("js/admin-inscription-salle.js",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .pour_utilisateur(request.user)
            .select_related("candidat__utilisateur", "entite", "option", "salle")
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if self.get_object(request, object_id) is None:
            raise Http404
        return super().change_view(request, object_id, form_url, extra_context)

    def delete_view(self, request, object_id, extra_context=None):
        if self.get_object(request, object_id) is None:
            raise Http404
        return super().delete_view(request, object_id, extra_context)

    def has_module_permission(self, request):
        autorisees = entites_autorisees(request.user)
        return request.user.is_superuser or bool(
            autorisees is not None and autorisees.exists()
        )

    def has_view_permission(self, request, obj=None):
        return self._autorise(request.user, obj)

    def has_change_permission(self, request, obj=None):
        return self._autorise(request.user, obj)

    def get_readonly_fields(self, request, obj=None):
        champs = super().get_readonly_fields(request, obj)
        if request.user.is_superuser and obj is None:
            return tuple(champ for champ in champs if champ != "candidat")
        if request.user.is_superuser:
            return champs
        return (*champs, "statut")

    def has_delete_permission(self, request, obj=None):
        return self._autorise(request.user, obj)

    def has_add_permission(self, request):
        return request.user.is_superuser

    @staticmethod
    def _autorise(utilisateur, objet=None):
        autorisees = entites_autorisees(utilisateur)
        if utilisateur.is_superuser:
            return True
        if autorisees is None or not autorisees.exists():
            return False
        return objet is None or autorisees.filter(pk=objet.entite_id).exists()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        autorisees = entites_autorisees(request.user)
        if autorisees is not None:
            if db_field.name == "entite":
                kwargs["queryset"] = autorisees
            elif db_field.name == "option":
                kwargs["queryset"] = db_field.related_model.objects.filter(
                    entite__in=autorisees
                )
        if db_field.name == "salle":
            salles = Salle.objects.all()
            if autorisees is not None:
                salles = salles.filter(entite__in=autorisees)

            if request.method == "POST" and "entite" in request.POST:
                entite_id = request.POST.get("entite")
            else:
                resolver_match = getattr(request, "resolver_match", None)
                object_id = (
                    resolver_match.kwargs.get("object_id") if resolver_match else None
                )
                entite_id = (
                    self.get_queryset(request)
                    .filter(pk=object_id)
                    .values_list("entite_id", flat=True)
                    .first()
                    if object_id
                    else None
                )

            if entite_id:
                salles = salles.filter(entite_id=entite_id)
            elif request.method == "POST" and "entite" in request.POST:
                salles = salles.none()
            kwargs["queryset"] = salles
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.action(description="Valider les inscriptions sélectionnées")
    def valider_inscriptions(self, request, queryset):
        with transaction.atomic():
            for inscription in queryset.select_for_update():
                inscription.statut = Inscription.Statut.VALIDE
                inscription.save(update_fields=["statut"])
                JournalAction.objects.create(
                    utilisateur=request.user,
                    inscription=inscription,
                    entite=inscription.entite,
                    action=JournalAction.Action.VALIDATION,
                )
        self.message_user(
            request, "Les dossiers sélectionnés ont été validés.", messages.SUCCESS
        )

    @admin.action(description="Rejeter les inscriptions sélectionnées")
    def rejeter_inscriptions(self, request, queryset):
        with transaction.atomic():
            for inscription in queryset.select_for_update():
                inscription.statut = Inscription.Statut.REJETE
                inscription.save(update_fields=["statut"])
                JournalAction.objects.create(
                    utilisateur=request.user,
                    inscription=inscription,
                    entite=inscription.entite,
                    action=JournalAction.Action.REJET,
                )
        self.message_user(
            request, "Les dossiers sélectionnés ont été rejetés.", messages.SUCCESS
        )

    def save_model(self, request, obj, form, change):
        ancien_statut = None
        if change:
            ancien_statut = type(obj).objects.get(pk=obj.pk).statut
        super().save_model(request, obj, form, change)
        if change and ancien_statut != obj.statut:
            JournalAction.objects.create(
                utilisateur=request.user,
                inscription=obj,
                entite=obj.entite,
                action=JournalAction.Action.MODIFICATION_STATUT,
                details={
                    "ancien_statut": ancien_statut,
                    "nouveau_statut": obj.statut,
                },
            )

    def delete_model(self, request, obj):
        JournalAction.objects.create(
            utilisateur=request.user,
            inscription=obj,
            entite=obj.entite,
            action=JournalAction.Action.SUPPRESSION,
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            for inscription in queryset:
                JournalAction.objects.create(
                    utilisateur=request.user,
                    inscription=inscription,
                    entite=inscription.entite,
                    action=JournalAction.Action.SUPPRESSION,
                )
            queryset.delete()


class BaseAdminEntite(admin.ModelAdmin):
    def get_queryset(self, request):
        autorisees = entites_autorisees(request.user)
        queryset = super().get_queryset(request)
        return (
            queryset if autorisees is None else queryset.filter(entite__in=autorisees)
        )

    def has_module_permission(self, request):
        autorisees = entites_autorisees(request.user)
        return request.user.is_superuser or bool(
            autorisees is not None and autorisees.exists()
        )

    def has_view_permission(self, request, obj=None):
        return self._autorise(request.user, obj)

    def has_add_permission(self, request):
        return self._autorise(request.user)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if self.get_object(request, object_id) is None:
            raise Http404
        return super().change_view(request, object_id, form_url, extra_context)

    def delete_view(self, request, object_id, extra_context=None):
        if self.get_object(request, object_id) is None:
            raise Http404
        return super().delete_view(request, object_id, extra_context)

    def has_change_permission(self, request, obj=None):
        return self._autorise(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return self._autorise(request.user, obj)

    def _autorise(self, utilisateur, objet=None):
        autorisees = entites_autorisees(utilisateur)
        if utilisateur.is_superuser:
            return True
        if autorisees is None or not autorisees.exists():
            return False
        return objet is None or autorisees.filter(pk=objet.entite_id).exists()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        autorisees = entites_autorisees(request.user)
        if autorisees is not None and db_field.name == "entite":
            kwargs["queryset"] = autorisees
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Option)
class OptionAdmin(BaseAdminEntite):
    list_display = ("nom", "entite", "active")
    list_filter = (FiltreEntiteAutorisee, "active")
    actions = ("delete_selected", "activer_options", "desactiver_options")

    @admin.action(description="Activer les options sélectionnées")
    def activer_options(self, request, queryset):
        nombre = queryset.update(active=True)
        self.message_user(request, f"{nombre} option(s) activée(s).")

    @admin.action(description="Désactiver les options sélectionnées")
    def desactiver_options(self, request, queryset):
        nombre = queryset.update(active=False)
        self.message_user(request, f"{nombre} option(s) désactivée(s).")

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser or obj is None:
            return ()
        return ("entite",)


@admin.register(Salle)
class SalleAdmin(BaseAdminEntite):
    list_display = ("nom", "entite", "capacite")
    list_filter = (FiltreEntiteAutorisee,)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        identifiant_entite = request.GET.get("entite")
        if identifiant_entite:
            entites = Entite.objects.all()
            autorisees = entites_autorisees(request.user)
            if autorisees is not None:
                entites = entites.filter(pk__in=autorisees)
            entite = entites.filter(pk=identifiant_entite).first()
            if entite:
                initial["entite"] = entite.pk
            else:
                initial.pop("entite", None)
        return initial

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser or obj is None:
            return ()
        return ("entite",)


@admin.register(HoraireEntite)
class HoraireEntiteAdmin(BaseAdminEntite):
    list_display = ("entite", "code", "actif")
    list_filter = (FiltreEntiteAutorisee, "actif")
    actions = ("delete_selected", "activer_horaires", "desactiver_horaires")

    @admin.action(description="Activer les horaires sélectionnés")
    def activer_horaires(self, request, queryset):
        nombre = queryset.update(actif=True)
        self.message_user(request, f"{nombre} horaire(s) activé(s).")

    @admin.action(description="Désactiver les horaires sélectionnés")
    def desactiver_horaires(self, request, queryset):
        nombre = queryset.update(actif=False)
        self.message_user(request, f"{nombre} horaire(s) désactivé(s).")

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser or obj is None:
            return ()
        return ("entite",)


@admin.register(Entite)
class EntiteAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "email_contact", "active", "inscription_ouverte")
    list_filter = ("active", "inscription_ouverte")
    search_fields = ("code", "nom", "email_contact")
    actions = (
        "delete_selected",
        "activer_entites",
        "desactiver_entites",
        "ouvrir_inscriptions",
        "fermer_inscriptions",
    )

    @admin.action(description="Activer les entités sélectionnées")
    def activer_entites(self, request, queryset):
        nombre = queryset.update(active=True)
        self.message_user(request, f"{nombre} entité(s) activée(s).")

    @admin.action(description="Désactiver les entités sélectionnées")
    def desactiver_entites(self, request, queryset):
        nombre = queryset.update(active=False)
        self.message_user(request, f"{nombre} entité(s) désactivée(s).")

    @admin.action(description="Ouvrir les inscriptions sélectionnées")
    def ouvrir_inscriptions(self, request, queryset):
        nombre = queryset.update(inscription_ouverte=True)
        self.message_user(request, f"Inscriptions ouvertes pour {nombre} entité(s).")

    @admin.action(description="Fermer les inscriptions sélectionnées")
    def fermer_inscriptions(self, request, queryset):
        nombre = queryset.update(inscription_ouverte=False)
        self.message_user(request, f"Inscriptions fermées pour {nombre} entité(s).")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(AdministrateurEntite)
class AdministrateurEntiteAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "entite")
    search_fields = ("utilisateur__email", "entite__nom")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not obj.utilisateur.is_superuser and obj.utilisateur.is_staff:
            obj.utilisateur.is_staff = False
            obj.utilisateur.save(update_fields=["is_staff"])
        EmailAddress.objects.update_or_create(
            user=obj.utilisateur,
            email=obj.utilisateur.email,
            defaults={"primary": True, "verified": True},
        )
