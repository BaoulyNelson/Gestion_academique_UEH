from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from applications.administration.mixins import EntiteAdminRequiredMixin
from applications.candidats.models import Candidat
from applications.candidatures.forms import BrouillonInscriptionForm, InscriptionForm
from applications.candidatures.models import BrouillonInscription, Inscription
from applications.candidatures.pdf import generer_pdf_inscription
from applications.candidatures.progression import (
    champs_adresse_manquants,
    champs_personnels_manquants,
    champs_profil_manquants,
    documents_manquants,
)
from applications.documents.models import DocumentCandidat
from applications.entites.models import Entite, HoraireEntite, entites_autorisees
from applications.resultats.models import Resultat


def inscription_visible_par(utilisateur, identifiant):
    if not utilisateur.is_authenticated:
        return get_object_or_404(Inscription, pk=identifiant, pk__in=[])
    if Candidat.objects.filter(
        utilisateur=utilisateur, inscriptions__pk=identifiant
    ).exists():
        return get_object_or_404(
            Inscription.objects.select_related(
                "candidat__utilisateur", "entite", "option", "salle"
            ),
            pk=identifiant,
        )
    return get_object_or_404(
        Inscription.objects.pour_utilisateur(utilisateur).select_related(
            "candidat__utilisateur", "entite", "option", "salle"
        ),
        pk=identifiant,
    )


def _contexte_formulaire_inscription(candidat, formulaire, brouillon):
    rangs_utilises = set(
        Inscription.objects.filter(candidat=candidat).values_list("rang", flat=True)
    )
    rang_prevu = next((rang for rang in range(3) if rang not in rangs_utilises), None)
    return {
        "formulaire": formulaire,
        "candidat": candidat,
        "brouillon": brouillon,
        "date_inscription": timezone.localdate(),
        "numero_dossier_prevu": (
            candidat.pk * 100 + rang_prevu if rang_prevu is not None else ""
        ),
    }


@login_required
@ratelimit(key="user", rate="5/h", method="POST", block=True)
def creer_inscription(request):
    candidat = Candidat.objects.filter(utilisateur=request.user).first()
    if candidat is None:
        return render(
            request,
            "tableau_bord/acces_admission_refuse.html",
            {"page_publique": True},
            status=403,
        )
    if Inscription.objects.filter(candidat=candidat).count() >= 3:
        messages.error(request, "Vous avez atteint la limite de 3 inscriptions.")
        return redirect("tableau_bord:mes_inscriptions")

    if champs_personnels_manquants(candidat) or documents_manquants(candidat):
        etape_manquante = 1
    elif champs_adresse_manquants(candidat):
        etape_manquante = 2
    elif not candidat.ecoles.exists():
        etape_manquante = 3
    else:
        etape_manquante = None

    if etape_manquante:
        request.session["reprendre_candidature"] = True
        messages.info(request, "Reprenez votre profil à la première étape incomplète.")
        return redirect(f"{reverse('candidats:mon_profil')}?etape={etape_manquante}")

    brouillon, _ = BrouillonInscription.objects.get_or_create(candidat=candidat)
    if request.method == "POST":
        formulaire = InscriptionForm(
            request.POST,
            request.FILES,
            instance=Inscription(candidat=candidat),
        )
        formulaire_brouillon = BrouillonInscriptionForm(
            request.POST, request.FILES, instance=brouillon
        )
        entite_demandee = Entite.objects.filter(
            pk=request.POST.get("entite"), active=True
        ).first()
        if entite_demandee and not entite_demandee.inscription_ouverte:
            formulaire.add_error(
                "entite", "Les inscriptions sont fermées pour cette entité."
            )
            return render(
                request,
                "candidatures/creer.html",
                _contexte_formulaire_inscription(candidat, formulaire, brouillon),
                status=400,
            )
        if request.POST.get("action") == "brouillon":
            if formulaire_brouillon.is_valid():
                formulaire_brouillon.save()
                messages.success(
                    request,
                    "Votre brouillon est enregistré. Vous pourrez le reprendre ici.",
                )
                return redirect("candidatures:creer")
            formulaire.add_error(None, "Le brouillon n’a pas pu être enregistré.")
        elif formulaire_brouillon.is_valid():
            formulaire_brouillon.save()
        if formulaire.is_valid():
            inscription = formulaire.save(commit=False)
            inscription.candidat = candidat
            if not inscription.recu_paiement and brouillon.recu_paiement:
                inscription.recu_paiement = brouillon.recu_paiement
            try:
                inscription.save()
            except ValidationError as erreur:
                formulaire.add_error(None, erreur)
            else:
                brouillon.delete()
                request.session.pop("reprendre_candidature", None)
                from applications.notifications.tasks import (
                    envoyer_confirmation_inscription,
                )

                envoyer_confirmation_inscription.delay(inscription.pk)
                messages.success(
                    request,
                    f"Votre dossier #{inscription.numero_dossier} a été envoyé.",
                )
                return redirect("candidatures:detail", pk=inscription.pk)
    else:
        date_depot = brouillon.date_depot
        if date_depot is None:
            date_depot = (
                Inscription.objects.filter(candidat=candidat, date_depot__isnull=False)
                .order_by("-date_inscription", "-pk")
                .values_list("date_depot", flat=True)
                .first()
            )
        formulaire = InscriptionForm(
            initial={
                "entite": brouillon.entite_id,
                "option": brouillon.option_id,
                "annee_academique": brouillon.annee_academique,
                "horaire": brouillon.horaire,
                "seq": brouillon.seq,
                "till": brouillon.till,
                "date_depot": date_depot,
                "recu_paiement": brouillon.recu_paiement,
            }
        )
    return render(
        request,
        "candidatures/creer.html",
        _contexte_formulaire_inscription(candidat, formulaire, brouillon),
    )


@login_required
@require_POST
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def sauvegarder_brouillon_inscription(request):
    candidat = get_object_or_404(Candidat, utilisateur=request.user)
    if champs_profil_manquants(candidat) or documents_manquants(candidat):
        return JsonResponse(
            {"enregistre": False, "erreur": "Les étapes précédentes sont incomplètes."},
            status=400,
        )
    brouillon, _ = BrouillonInscription.objects.get_or_create(candidat=candidat)
    formulaire = BrouillonInscriptionForm(
        request.POST, request.FILES, instance=brouillon
    )
    if not formulaire.is_valid():
        return JsonResponse(
            {"enregistre": False, "erreurs": formulaire.errors.get_json_data()},
            status=400,
        )
    formulaire.save()
    return JsonResponse({"enregistre": True})


@login_required
def choix_entite(request):
    entite = get_object_or_404(
        Entite.objects.filter(active=True, inscription_ouverte=True),
        pk=request.GET.get("entite"),
    )
    options = list(
        entite.options.filter(active=True).order_by("nom").values("id", "nom")
    )
    horaires = [
        {"code": horaire.code, "nom": horaire.get_code_display()}
        for horaire in entite.horaires.filter(actif=True).order_by("code")
    ]
    return JsonResponse({"options": options, "horaires": horaires})


@login_required
def detail_inscription(request, pk):
    inscription = get_object_or_404(
        Inscription.objects.select_related(
            "candidat__utilisateur", "entite", "option", "salle"
        ).prefetch_related(
            "candidat__documents",
            "candidat__ecoles",
            "candidat__parcours_etudes",
        ),
        pk=pk,
        candidat__utilisateur=request.user,
    )
    parcours_apercus = []
    for etude in inscription.candidat.parcours_etudes.all():
        documents_etude = []
        for champ, titre in (
            ("certificat", "Certificat/Relevé"),
            ("lettre_recommandation", "Lettre de recommandation"),
            ("lettre_motivation", "Lettre de motivation"),
            ("cv_ou_autre_document", "CV / autre document"),
        ):
            if getattr(etude, champ):
                documents_etude.append(
                    {
                        "titre": titre,
                        "apercu": reverse(
                            "candidats:apercu_parcours", args=[etude.pk, champ]
                        ),
                        "telecharger": reverse(
                            "candidats:document_parcours", args=[etude.pk, champ]
                        ),
                    }
                )
        parcours_apercus.append({"etude": etude, "documents": documents_etude})
    return render(
        request,
        "candidatures/detail.html",
        {
            "inscription": inscription,
            "candidat": inscription.candidat,
            "documents": inscription.candidat.documents.all(),
            "ecoles": inscription.candidat.ecoles.all(),
            "parcours": inscription.candidat.parcours_etudes.all(),
            "parcours_apercus": parcours_apercus,
        },
    )


@login_required
def recu_inscription(request, pk):
    inscription = inscription_visible_par(request.user, pk)
    fiche_paiement = (
        DocumentCandidat.objects.filter(
            candidat=inscription.candidat,
            type_document=DocumentCandidat.TypeDocument.PAIEMENT,
        )
        .order_by("-date_televersement")
        .first()
    )
    return render(
        request,
        "candidatures/recu.html",
        {"inscription": inscription, "fiche_paiement": fiche_paiement},
    )


@login_required
def telecharger_recu_paiement(request, pk):
    inscription = inscription_visible_par(request.user, pk)
    if not inscription.recu_paiement:
        raise Http404
    return FileResponse(
        inscription.recu_paiement.open("rb"),
        as_attachment=True,
        filename=inscription.recu_paiement.name.rsplit("/", 1)[-1],
    )


@login_required
def pdf_inscription(request, pk):
    inscription = inscription_visible_par(request.user, pk)
    reponse = HttpResponse(
        generer_pdf_inscription(inscription), content_type="application/pdf"
    )
    reponse["Content-Disposition"] = (
        f'attachment; filename="dossier-{inscription.numero_dossier}.pdf"'
    )
    return reponse


@login_required
def mes_resultats(request):
    candidat = get_object_or_404(Candidat, utilisateur=request.user)
    resultats = Resultat.objects.filter(
        inscription__candidat=candidat, publie=True
    ).select_related("inscription__entite")
    return render(request, "resultats/mes_resultats.html", {"resultats": resultats})


@login_required
def liste_inscriptions_administrateur(request):
    from applications.administration.mixins import EntiteAdminRequiredMixin

    autorisees = entites_autorisees(request.user)
    if not request.user.is_superuser and (
        autorisees is None or not autorisees.exists()
    ):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("Vous n’êtes administrateur d’aucune entité.")
    inscriptions = Inscription.objects.pour_utilisateur(request.user).select_related(
        "candidat__utilisateur", "entite", "option", "salle"
    )
    return render(
        request,
        "administration/liste_inscriptions.html",
        {"inscriptions": inscriptions},
    )
