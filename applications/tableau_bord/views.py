from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from applications.candidats.models import Candidat
from applications.candidatures.models import BrouillonInscription
from applications.candidatures.models import Inscription
from applications.candidatures.progression import (
    champs_profil_manquants,
    documents_manquants,
)
from applications.entites.models import Entite, Option, entites_autorisees
from applications.resultats.models import Resultat


def accueil(request, rubrique="accueil"):
    entites = Entite.objects.filter(active=True).prefetch_related(
        Prefetch("options", queryset=Option.objects.filter(active=True))
    )
    aujourd_hui = timezone.localdate()
    debut_periode = aujourd_hui - timedelta(days=29)
    inscriptions = Inscription.objects.all()

    entites_avec_inscriptions = Entite.objects.filter(active=True).annotate(
        nombre_inscriptions=Count("inscriptions")
    )
    inscriptions_par_sexe = {choix: 0 for choix, _ in Candidat.Sexe.choices}
    inscriptions_par_sexe[""] = 0
    for ligne in inscriptions.values("candidat__sexe").annotate(total=Count("pk")):
        sexe = ligne["candidat__sexe"] or ""
        inscriptions_par_sexe[sexe] = ligne["total"]

    inscriptions_par_departement = {
        choix: 0 for choix, _ in Candidat.Departement.choices
    }
    inscriptions_par_departement[""] = 0
    for ligne in inscriptions.values("candidat__departement_geographique").annotate(
        total=Count("pk")
    ):
        departement = ligne["candidat__departement_geographique"] or ""
        inscriptions_par_departement[departement] = ligne["total"]

    inscriptions_quotidiennes = {
        ligne["jour"]: ligne["total"]
        for ligne in (
            inscriptions.filter(
                date_inscription__date__gte=debut_periode,
                date_inscription__date__lte=aujourd_hui,
            )
            .annotate(jour=TruncDate("date_inscription"))
            .values("jour")
            .annotate(total=Count("pk"))
        )
    }
    jours = [debut_periode + timedelta(days=decalage) for decalage in range(30)]
    labels_sexe = {
        **dict(Candidat.Sexe.choices),
        "": "Non renseigné",
    }
    labels_departement = {
        **dict(Candidat.Departement.choices),
        "": "Non renseigné",
    }
    donnees_statistiques = {
        "entites": {
            "labels": [entite.code for entite in entites_avec_inscriptions],
            "valeurs": [
                entite.nombre_inscriptions for entite in entites_avec_inscriptions
            ],
        },
        "sexe": {
            "labels": [labels_sexe[choix] for choix in inscriptions_par_sexe],
            "valeurs": list(inscriptions_par_sexe.values()),
        },
        "departements": {
            "labels": [
                labels_departement[choix] for choix in inscriptions_par_departement
            ],
            "valeurs": list(inscriptions_par_departement.values()),
        },
        "evolution": {
            "labels": [jour.strftime("%d/%m") for jour in jours],
            "valeurs": [inscriptions_quotidiennes.get(jour, 0) for jour in jours],
        },
    }
    return render(
        request,
        "tableau_bord/accueil.html",
        {
            "page_publique": True,
            "rubrique": rubrique,
            "titre_page": {
                "accueil": "Admission UEH | Concours d'admission",
                "guide": "Guide du postulant | Admission UEH",
                "entites": "Entités participantes | Admission UEH",
                "statistiques": "Statistiques | Admission UEH",
                "a_propos": "À propos | Admission UEH",
            }[rubrique],
            "entites": entites,
            "nb_entites": entites.count(),
            "nb_inscriptions": inscriptions.count(),
            "nb_inscriptions_aujourdhui": inscriptions.filter(
                date_inscription__date=aujourd_hui
            ).count(),
            "nb_resultats_publies": Resultat.objects.filter(publie=True).count(),
            "donnees_statistiques": donnees_statistiques,
        },
    )


@login_required
def guide_documents(request):
    return render(request, "tableau_bord/guide_documents.html")


@login_required
def mes_inscriptions(request):
    if request.user.is_superuser:
        return redirect("admin:index")
    entites_gerees = entites_autorisees(request.user)
    if entites_gerees is not None and entites_gerees.exists():
        return redirect("administration:liste_inscriptions")
    candidat = Candidat.objects.filter(utilisateur=request.user).first()
    if candidat is None:
        return render(
            request,
            "tableau_bord/acces_admission_refuse.html",
            {"page_publique": True},
            status=403,
        )
    date_locale = timezone.localdate()
    debut_annee = date_locale.year if date_locale.month >= 8 else date_locale.year - 1
    annee = request.GET.get("annee", f"{debut_annee}-{debut_annee + 1}")
    toutes = Inscription.objects.filter(candidat=candidat).select_related(
        "entite", "option", "salle"
    )
    inscriptions = toutes.filter(annee_academique=annee) if annee else toutes
    inscriptions_precedentes = toutes.exclude(annee_academique=annee).order_by(
        "-date_inscription"
    )
    statistiques = toutes.aggregate(
        nb_validees=Count("id", filter=Q(statut=Inscription.Statut.VALIDE)),
        nb_attente=Count("id", filter=Q(statut=Inscription.Statut.EN_ATTENTE)),
        nb_total=Count("id"),
    )
    annees = (
        toutes.order_by("-annee_academique")
        .values_list("annee_academique", flat=True)
        .distinct()
    )
    return render(
        request,
        "tableau_bord/mes_inscriptions.html",
        {
            "candidat": candidat,
            "brouillon_existant": BrouillonInscription.objects.filter(
                candidat=candidat
            ).exists(),
            "etape_initiale_complete": not champs_profil_manquants(candidat)
            and not documents_manquants(candidat),
            "inscriptions": inscriptions,
            "inscriptions_precedentes": inscriptions_precedentes,
            "annees_academiques": annees,
            "annee_selectionnee": annee,
            **statistiques,
        },
    )
