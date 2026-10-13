from django.contrib import messages
from django.contrib.auth.decorators import login_required
from mimetypes import guess_type
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET

from applications.candidats.etapes_forms import (
    AdresseCandidatForm,
    choix_communes,
    EcoleCandidatForm,
    InformationsPersonnellesForm,
    ParcoursCandidatForm,
)
from applications.candidats.models import Candidat, EcoleCandidat, ParcoursCandidat
from applications.candidatures.progression import (
    champs_adresse_manquants,
    champs_personnels_manquants,
    documents_manquants,
)


def premiere_etape_incomplete(candidat):
    if champs_personnels_manquants(candidat) or documents_manquants(candidat):
        return 1
    if champs_adresse_manquants(candidat):
        return 2
    if not candidat.ecoles.exists():
        return 3
    return 4


def _continuer_apres_profil(request):
    reprendre_candidature = request.session.pop("reprendre_candidature", False)
    messages.success(request, "Votre profil est terminé.")
    if reprendre_candidature:
        return redirect("candidatures:creer")
    return redirect("tableau_bord:mes_inscriptions")


@login_required
def mon_profil(request):
    if request.user.is_staff:
        return redirect("tableau_bord:mes_inscriptions")
    candidat = get_object_or_404(Candidat, utilisateur=request.user)
    try:
        etape = int(request.POST.get("etape") or request.GET.get("etape", 1))
    except (TypeError, ValueError):
        etape = 1
    etape = min(max(etape, 1), 4)
    etape_minimale = premiere_etape_incomplete(candidat)
    if etape > etape_minimale:
        return redirect(f"{reverse('candidats:mon_profil')}?etape={etape_minimale}")

    formulaire = None
    if etape == 1:
        formulaire = InformationsPersonnellesForm(
            request.POST or None,
            request.FILES or None,
            instance=candidat,
            utilisateur=request.user,
        )
        if request.method == "POST" and formulaire.is_valid():
            formulaire.save()
            messages.success(request, "Informations personnelles enregistrées.")
            return redirect(f"{reverse('candidats:mon_profil')}?etape=2")
    elif etape == 2:
        formulaire = AdresseCandidatForm(
            request.POST or None,
            instance=candidat,
        )
        if request.method == "POST" and request.POST.get("action") == "retour":
            if formulaire.is_valid():
                formulaire.save()
            return redirect(f"{reverse('candidats:mon_profil')}?etape=1")
        if request.method == "POST" and formulaire.is_valid():
            formulaire.save()
            messages.success(request, "Adresse enregistrée.")
            return redirect(f"{reverse('candidats:mon_profil')}?etape=3")
    elif etape == 3:
        ecoles = candidat.ecoles.all()
        formulaire = EcoleCandidatForm(
            request.POST or None,
            request.FILES or None,
            ecole_existante=ecoles.exists(),
        )
        if request.method == "POST" and request.POST.get("action") == "retour":
            if formulaire.is_valid() and formulaire.cleaned_data.get("nom"):
                ecole = formulaire.save(commit=False)
                ecole.candidat = candidat
                ecole.save()
            return redirect(f"{reverse('candidats:mon_profil')}?etape=2")
        if request.method == "POST" and formulaire.is_valid():
            if formulaire.cleaned_data.get("nom"):
                ecole = formulaire.save(commit=False)
                ecole.candidat = candidat
                ecole.save()
                if not candidat.etablissement_scolaire:
                    candidat.etablissement_scolaire = ecole.nom
                    candidat.save(update_fields=["etablissement_scolaire"])
            if request.POST.get("action") == "retour":
                return redirect(f"{reverse('candidats:mon_profil')}?etape=2")
            messages.success(request, "Informations scolaires enregistrées.")
            return redirect(f"{reverse('candidats:mon_profil')}?etape=4")
    else:
        formulaire = ParcoursCandidatForm(
            request.POST or None,
            request.FILES or None,
        )
        if request.method == "POST" and request.POST.get("action") == "retour":
            if formulaire.is_valid() and formulaire.cleaned_data.get("etablissement"):
                parcours = formulaire.save(commit=False)
                parcours.candidat = candidat
                parcours.save()
            return redirect(f"{reverse('candidats:mon_profil')}?etape=3")
        if request.method == "POST" and formulaire.is_valid():
            action = request.POST.get("action")
            a_des_donnees = any(
                formulaire.cleaned_data.get(champ)
                for champ in (
                    "etablissement",
                    "niveau",
                    "programme",
                    "annee_obtention",
                    "type_document",
                    "certificat",
                    "lettre_recommandation",
                    "lettre_motivation",
                    "cv_ou_autre_document",
                )
            )
            etablissement = formulaire.cleaned_data.get("etablissement")
            if action == "ajouter":
                if not etablissement:
                    formulaire.add_error(
                        "etablissement",
                        "Indiquez un établissement avant d’enregistrer.",
                    )
                else:
                    parcours = formulaire.save(commit=False)
                    parcours.candidat = candidat
                    parcours.save()
                    messages.success(request, "Études et documents enregistrés.")
                    return redirect(f"{reverse('candidats:mon_profil')}?etape=4")
            else:
                if a_des_donnees and not etablissement:
                    formulaire.add_error(
                        "etablissement",
                        "Indiquez l’établissement associé à ces documents.",
                    )
                elif a_des_donnees:
                    parcours = formulaire.save(commit=False)
                    parcours.candidat = candidat
                    parcours.save()
                if not formulaire.errors:
                    return _continuer_apres_profil(request)

    if etape == 1:
        champs_etape = [
            formulaire[nom]
            for nom in (
                "prenom",
                "nom",
                "sexe",
                "date_naissance",
                "nationalite",
                "email",
                "telephone",
                "nom_parent_responsable",
                "lieu_naissance",
                "ninu",
                "nif",
                "document_naissance",
                "photo_identite",
                "document_ninu",
                "document_nif",
            )
        ]
    elif etape == 2:
        champs_etape = [
            formulaire[nom] for nom in ("adresse", "departement_geographique", "ville")
        ]
    elif etape == 3:
        champs_etape = [formulaire[nom] for nom in ("nom", "zone", "certificat")]
    else:
        champs_etape = [formulaire[nom] for nom in formulaire.fields]

    return render(
        request,
        "candidats/profil.html",
        {
            "etape": etape,
            "etape_personnelle_complete": etape_minimale > 1,
            "etape_adresse_complete": etape_minimale > 2,
            "etape_ecole_complete": etape_minimale > 3,
            "etape_personnelle_active": etape == 1,
            "etape_adresse_active": etape == 2,
            "etape_ecole_active": etape == 3,
            "etape_etudes_active": etape == 4,
            "formulaire": formulaire,
            "champs_etape": champs_etape,
            "candidat": candidat,
            "documents_existants": {
                document.type_document: document
                for document in candidat.documents.all()
            },
            "ecoles": candidat.ecoles.all(),
            "parcours": candidat.parcours_etudes.all(),
        },
    )


@login_required
@require_GET
def communes_departement(request):
    departement = request.GET.get("departement", "")
    choix = choix_communes(departement)
    return JsonResponse(
        {"communes": [{"value": valeur, "label": label} for valeur, label in choix]}
    )


@login_required
def photo_identite(request):
    candidat = get_object_or_404(Candidat, utilisateur=request.user)
    document = candidat.photo_identite
    if not document:
        raise Http404
    reponse = FileResponse(
        document.fichier.open("rb"),
        as_attachment=False,
        filename=document.fichier.name.rsplit("/", 1)[-1],
    )
    reponse["Cache-Control"] = "private, no-store"
    return reponse


@login_required
def telecharger_ecole(request, pk):
    ecole = get_object_or_404(
        EcoleCandidat.objects.select_related("candidat__utilisateur"),
        pk=pk,
        candidat__utilisateur=request.user,
    )
    return FileResponse(
        ecole.certificat.open("rb"),
        as_attachment=True,
        filename=ecole.certificat.name.rsplit("/", 1)[-1],
    )


@login_required
@xframe_options_sameorigin
def apercu_ecole(request, pk):
    ecole = get_object_or_404(
        EcoleCandidat.objects.select_related("candidat__utilisateur"),
        pk=pk,
        candidat__utilisateur=request.user,
    )
    nom_fichier = ecole.certificat.name.rsplit("/", 1)[-1]
    reponse = FileResponse(
        ecole.certificat.open("rb"),
        as_attachment=False,
        filename=nom_fichier,
        content_type=guess_type(nom_fichier)[0] or "application/octet-stream",
    )
    reponse["Cache-Control"] = "private, no-store"
    reponse["X-Content-Type-Options"] = "nosniff"
    return reponse


@login_required
def telecharger_parcours(request, pk, champ):
    champs_autorises = {
        "certificat",
        "lettre_recommandation",
        "lettre_motivation",
        "cv_ou_autre_document",
    }
    if champ not in champs_autorises:
        raise Http404
    parcours = get_object_or_404(
        ParcoursCandidat.objects.select_related("candidat__utilisateur"),
        pk=pk,
        candidat__utilisateur=request.user,
    )
    fichier = getattr(parcours, champ)
    if not fichier:
        raise Http404
    return FileResponse(
        fichier.open("rb"),
        as_attachment=True,
        filename=fichier.name.rsplit("/", 1)[-1],
    )


@login_required
@xframe_options_sameorigin
def apercu_parcours(request, pk, champ):
    champs_autorises = {
        "certificat",
        "lettre_recommandation",
        "lettre_motivation",
        "cv_ou_autre_document",
    }
    if champ not in champs_autorises:
        raise Http404
    parcours = get_object_or_404(
        ParcoursCandidat.objects.select_related("candidat__utilisateur"),
        pk=pk,
        candidat__utilisateur=request.user,
    )
    fichier = getattr(parcours, champ)
    if not fichier:
        raise Http404
    nom_fichier = fichier.name.rsplit("/", 1)[-1]
    reponse = FileResponse(
        fichier.open("rb"),
        as_attachment=False,
        filename=nom_fichier,
        content_type=guess_type(nom_fichier)[0] or "application/octet-stream",
    )
    reponse["Cache-Control"] = "private, no-store"
    reponse["X-Content-Type-Options"] = "nosniff"
    return reponse
