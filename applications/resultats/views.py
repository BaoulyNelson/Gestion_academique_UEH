from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from applications.candidats.models import Candidat
from applications.candidatures.models import Inscription
from applications.entites.models import entites_autorisees
from applications.resultats.models import Resultat
from applications.resultats.pdf import generer_pdf_ticket_resultat


@login_required
def mes_resultats(request):
    autorisees = entites_autorisees(request.user)
    if request.user.is_superuser or (autorisees is not None and autorisees.exists()):
        inscriptions = list(
            Inscription.objects.pour_utilisateur(request.user)
            .select_related("candidat__utilisateur", "entite", "option", "salle")
            .order_by("-date_inscription", "-pk")
        )
        resultats = Resultat.objects.filter(
            inscription_id__in=[inscription.pk for inscription in inscriptions]
        ).prefetch_related("epreuves")
        resultats_par_inscription = {
            resultat.inscription_id: resultat for resultat in resultats
        }
        for inscription in inscriptions:
            inscription.resultat_admin = resultats_par_inscription.get(inscription.pk)
        return render(
            request,
            "resultats/mes_resultats.html",
            {"vue_administration": True, "inscriptions": inscriptions},
        )

    candidat = get_object_or_404(Candidat, utilisateur=request.user)
    resultats = (
        Resultat.objects.filter(inscription__candidat=candidat, publie=True)
        .select_related("inscription__entite", "inscription__candidat__utilisateur")
        .prefetch_related("epreuves")
    )
    return render(request, "resultats/mes_resultats.html", {"resultats": resultats})


@login_required
def imprimer_resultat(request, pk):
    resultat = get_object_or_404(
        Resultat.objects.filter(
            inscription__candidat__utilisateur=request.user,
            publie=True,
        )
        .select_related(
            "inscription__candidat__utilisateur",
            "inscription__entite",
            "inscription__option",
        )
        .prefetch_related("epreuves"),
        pk=pk,
    )
    reponse = HttpResponse(
        generer_pdf_ticket_resultat(resultat), content_type="application/pdf"
    )
    reponse["Content-Disposition"] = (
        f'attachment; filename="resultat-{resultat.inscription.numero_dossier}.pdf"'
    )
    return reponse
