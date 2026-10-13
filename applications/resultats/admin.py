import csv

from django.contrib import admin
from django import forms
from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone

from applications.candidatures.models import Inscription
from applications.entites.models import entites_autorisees
from applications.resultats.models import EpreuveResultat, Resultat


def charger_choix_matieres(inscription=None):
    groupes = {}
    chemin = settings.BASE_DIR / "data" / "matieres.csv"
    with chemin.open(encoding="utf-8-sig", newline="") as fichier:
        for ligne in csv.DictReader(fichier):
            code = (ligne.get("code_entite") or "").strip()
            option = (ligne.get("option") or "").strip()
            matiere = (ligne.get("matiere") or "").strip()
            if not code or not matiere:
                continue
            if inscription:
                if code != inscription.entite.code:
                    continue
                if option and (
                    not inscription.option_id or option != inscription.option.nom
                ):
                    continue
            groupe = f"{code} — {option}" if option else code
            groupes.setdefault(groupe, set()).add(matiere)
    return [
        (groupe, [(matiere, matiere) for matiere in sorted(matieres, key=str.casefold)])
        for groupe, matieres in sorted(
            groupes.items(), key=lambda item: item[0].casefold()
        )
    ]


class EpreuveResultatForm(forms.ModelForm):
    nom = forms.CharField(
        label="Matière",
        help_text="Choisissez une suggestion ou saisissez une matière.",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )

    class Meta:
        model = EpreuveResultat
        fields = ("nom", "note", "bareme", "coefficient", "ordre")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nom"].widget.attrs["placeholder"] = "Choisir ou saisir une matière"


class EpreuveResultatInline(admin.TabularInline):
    model = EpreuveResultat
    form = EpreuveResultatForm
    extra = 1
    ordering = ("ordre", "pk")


@admin.register(Resultat)
class ResultatAdmin(admin.ModelAdmin):
    list_display = (
        "inscription",
        "candidat",
        "entite",
        "decision_admission",
        "note",
        "publie",
        "date_publication",
    )
    list_filter = ("publie", "inscription__entite")
    search_fields = (
        "inscription__numero_dossier",
        "inscription__candidat__utilisateur__nom",
        "inscription__candidat__utilisateur__prenom",
        "inscription__candidat__utilisateur__email",
        "inscription__entite__nom",
    )
    autocomplete_fields = ("inscription",)
    readonly_fields = ("date_publication", "admis_calcule")
    exclude = ("admis",)
    inlines = (EpreuveResultatInline,)
    actions = ("delete_selected", "publier_resultats", "depublier_resultats")

    class Media:
        js = ("js/admin-resultats-matieres.js",)

    @admin.action(description="Publier les résultats sélectionnés")
    def publier_resultats(self, request, queryset):
        nombre = queryset.filter(publie=False).update(
            publie=True,
            date_publication=timezone.now(),
        )
        self.message_user(request, f"{nombre} résultat(s) publié(s).")

    @admin.action(description="Dépublier les résultats sélectionnés")
    def depublier_resultats(self, request, queryset):
        nombre = queryset.filter(publie=True).update(
            publie=False,
            date_publication=None,
        )
        self.message_user(request, f"{nombre} résultat(s) dépublié(s).")

    def get_urls(self):
        urls = super().get_urls()
        urls_personnalisees = [
            path(
                "matieres-inscription/",
                self.admin_site.admin_view(self.matieres_pour_inscription),
                name="resultats_resultat_matieres",
            )
        ]
        return urls_personnalisees + urls

    def matieres_pour_inscription(self, request):
        inscription = get_object_or_404(
            Inscription.objects.select_related("entite", "option"),
            pk=request.GET.get("inscription"),
        )
        if not self._peut_gerer_entite(request.user, inscription.entite_id):
            raise Http404
        return JsonResponse(
            {
                "groupes": [
                    {
                        "nom": nom,
                        "matieres": [valeur for valeur, _ in choix],
                    }
                    for nom, choix in charger_choix_matieres(inscription)
                ]
            }
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "inscription":
            autorisees = entites_autorisees(request.user)
            if autorisees is not None:
                kwargs["queryset"] = Inscription.objects.filter(entite__in=autorisees)
        champ = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "inscription":
            champ.widget.attrs["data-url-matieres"] = reverse(
                "admin:resultats_resultat_matieres"
            )
        return champ

    def has_module_permission(self, request):
        autorisees = entites_autorisees(request.user)
        return request.user.is_superuser or bool(
            autorisees is not None and autorisees.exists()
        )

    def has_view_permission(self, request, obj=None):
        return self._autorise(request.user, obj)

    def has_add_permission(self, request):
        return self._autorise(request.user)

    def has_change_permission(self, request, obj=None):
        return self._autorise(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @staticmethod
    def _peut_gerer_entite(utilisateur, entite_id):
        autorisees = entites_autorisees(utilisateur)
        return utilisateur.is_superuser or bool(
            autorisees is not None and autorisees.filter(pk=entite_id).exists()
        )

    @classmethod
    def _autorise(cls, utilisateur, objet=None):
        autorisees = entites_autorisees(utilisateur)
        if utilisateur.is_superuser:
            return True
        if autorisees is None or not autorisees.exists():
            return False
        return (
            objet is None or autorisees.filter(pk=objet.inscription.entite_id).exists()
        )

    @admin.display(description="Candidat")
    def candidat(self, obj):
        utilisateur = obj.inscription.candidat.utilisateur
        return utilisateur.get_full_name() or utilisateur.email

    @admin.display(description="Entité")
    def entite(self, obj):
        return obj.inscription.entite

    @admin.display(description="Décision")
    def decision_admission(self, obj):
        return "Admis" if obj.admis_calcule else "Non admis"

    def get_queryset(self, request):
        queryset = (
            super()
            .get_queryset(request)
            .select_related("inscription__candidat__utilisateur", "inscription__entite")
        )
        autorisees = entites_autorisees(request.user)
        return (
            queryset
            if autorisees is None
            else queryset.filter(inscription__entite__in=autorisees)
        )

    def save_model(self, request, obj, form, change):
        if obj.publie and obj.date_publication is None:
            obj.date_publication = timezone.now()
        elif not obj.publie:
            obj.date_publication = None
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        resultat = form.instance
        resultat.note = resultat.moyenne_calculee
        resultat.admis = resultat.admis_calcule
        Resultat.objects.filter(pk=resultat.pk).update(
            note=resultat.note,
            admis=resultat.admis,
        )
