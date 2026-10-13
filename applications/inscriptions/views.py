from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from applications.audit.models import JournalAction
from applications.comptes.models import ProfilEtudiant, Utilisateur
from applications.referentiels.models import (
    AffectationCours,
    Cours,
    PeriodeAcademique,
)

from .forms import (
    FormulaireInscriptionPedagogique,
    FormulairePaiementScolarite,
    FormulaireRechercheDossier,
    FormulaireSelectionCours,
)
from .documents import generer_recu_paiement_pdf
from .models import (
    InscriptionPedagogique,
    PaiementScolarite,
    SelectionCours,
    TarifScolarite,
)
from .services.paiements import (
    frais_scolarite_acquittes,
    montant_scolarite_confirme,
)


@login_required
def liste_cours_professeur(request):
    if request.user.role != Utilisateur.Role.PROFESSEUR:
        raise PermissionDenied

    affectations = list(
        AffectationCours.objects.filter(professeur=request.user).select_related(
            "cours", "cours__programme", "periode"
        )
    )
    etudiants_par_cours = defaultdict(list)
    selections = (
        SelectionCours.objects.filter(
            cours__affectations_professeurs__professeur=request.user,
            cours__affectations_professeurs__periode_id=F("inscription__periode_id"),
            inscription__statut=InscriptionPedagogique.Statut.VALIDEE,
        )
        .select_related("inscription__etudiant", "inscription__programme", "cours")
        .order_by("cours__code", "inscription__etudiant__last_name")
    )
    for selection in selections:
        cle = (selection.cours_id, selection.inscription.periode_id)
        etudiants_par_cours[cle].append(selection)

    for affectation in affectations:
        cle = (affectation.cours_id, affectation.periode_id)
        affectation.etudiants_inscrits = etudiants_par_cours[cle]

    return render(
        request,
        "inscriptions/cours_professeur.django",
        {"affectations": affectations},
    )


@login_required
def liste_etudiants_professeur(request):
    if request.user.role != Utilisateur.Role.PROFESSEUR:
        raise PermissionDenied

    cours = (
        Cours.objects.filter(affectations_professeurs__professeur=request.user)
        .distinct()
        .order_by("code")
    )
    periodes = (
        PeriodeAcademique.objects.filter(affectations_cours__professeur=request.user)
        .distinct()
        .order_by("-annee_academique", "nom")
    )
    selections = (
        SelectionCours.objects.filter(
            cours__affectations_professeurs__professeur=request.user,
            cours__affectations_professeurs__periode_id=F("inscription__periode_id"),
            inscription__statut=InscriptionPedagogique.Statut.VALIDEE,
        )
        .select_related(
            "cours",
            "cours__programme",
            "inscription__etudiant",
            "inscription__etudiant__profil_etudiant",
            "inscription__programme",
            "inscription__periode",
        )
        .order_by(
            "cours__code",
            "inscription__periode__annee_academique",
            "inscription__etudiant__last_name",
            "inscription__etudiant__first_name",
        )
    )

    cours_selectionne = request.GET.get("cours", "")
    periode_selectionnee = request.GET.get("periode", "")
    try:
        cours_id = int(cours_selectionne) if cours_selectionne else None
    except ValueError:
        cours_id = None
    try:
        periode_id = int(periode_selectionnee) if periode_selectionnee else None
    except ValueError:
        periode_id = None

    if cours_id is not None:
        selections = selections.filter(cours_id=cours_id)
    if periode_id is not None:
        selections = selections.filter(inscription__periode_id=periode_id)

    return render(
        request,
        "inscriptions/etudiants_professeur.django",
        {
            "cours": cours,
            "periodes": periodes,
            "cours_selectionne": cours_selectionne,
            "periode_selectionnee": periode_selectionnee,
            "selections": selections,
        },
    )


@login_required
def liste_professeurs_etudiant(request):
    if request.user.role != Utilisateur.Role.ETUDIANT:
        raise PermissionDenied

    affectations = (
        AffectationCours.objects.filter(
            cours__selections_inscription__inscription__etudiant=request.user,
            cours__selections_inscription__inscription__statut=(
                InscriptionPedagogique.Statut.VALIDEE
            ),
            periode_id=F("cours__selections_inscription__inscription__periode_id"),
        )
        .select_related("professeur", "cours__programme", "periode")
        .distinct()
        .order_by(
            "periode__annee_academique",
            "cours__code",
            "professeur__last_name",
            "professeur__first_name",
        )
    )
    return render(
        request,
        "inscriptions/professeurs_etudiant.django",
        {"affectations": affectations},
    )


@login_required
def liste_cours_etudiant(request):
    if request.user.role != Utilisateur.Role.ETUDIANT:
        raise PermissionDenied

    selections = list(
        SelectionCours.objects.filter(
            inscription__etudiant=request.user,
            inscription__statut=InscriptionPedagogique.Statut.VALIDEE,
            inscription__conditions_passage_verifiees=True,
        )
        .select_related(
            "cours",
            "cours__programme",
            "inscription__periode",
        )
        .order_by(
            "inscription__periode__annee_academique",
            "inscription__periode__nom",
            "cours__code",
        )
    )
    affectations = AffectationCours.objects.filter(
        cours_id__in={selection.cours_id for selection in selections},
        periode_id__in={selection.inscription.periode_id for selection in selections},
    ).select_related("professeur")
    professeurs_par_cours_periode = defaultdict(list)
    for affectation in affectations:
        professeurs_par_cours_periode[
            (affectation.cours_id, affectation.periode_id)
        ].append(affectation.professeur)

    for selection in selections:
        selection.professeurs = professeurs_par_cours_periode[
            (selection.cours_id, selection.inscription.periode_id)
        ]

    return render(
        request,
        "inscriptions/cours_etudiant.django",
        {"selections": selections},
    )


@login_required
def paiements_etudiant(request):
    if request.user.role != Utilisateur.Role.ETUDIANT:
        raise PermissionDenied

    if request.method == "POST":
        formulaire = FormulairePaiementScolarite(request.POST, utilisateur=request.user)
        if formulaire.is_valid():
            paiement = formulaire.save(commit=False)
            paiement.etudiant = request.user
            paiement.full_clean()
            paiement.save()
            JournalAction.objects.create(
                utilisateur=request.user,
                action="paiement.declare",
                type_objet="PaiementScolarite",
                identifiant_objet=str(paiement.pk),
                details={"statut": paiement.statut},
                adresse_ip=request.META.get("REMOTE_ADDR"),
            )
            messages.success(request, "Votre paiement a ete transmis au registrariat.")
            return redirect("inscriptions:paiement_etudiant")
    else:
        formulaire = FormulairePaiementScolarite(utilisateur=request.user)

    paiements = PaiementScolarite.objects.filter(etudiant=request.user).select_related(
        "tarif__programme", "tarif__periode", "valide_par"
    )
    for paiement in paiements:
        paiement.total_confirme = montant_scolarite_confirme(
            request.user, paiement.tarif
        )
    return render(
        request,
        "inscriptions/paiements_etudiant.django",
        {
            "formulaire": formulaire,
            "paiements": paiements,
            "tarifs_disponibles": formulaire.fields["tarif"].queryset.exists(),
        },
    )


@login_required
def telecharger_recu_paiement(request, paiement_id):
    if request.user.role == Utilisateur.Role.ETUDIANT:
        paiements = PaiementScolarite.objects.filter(etudiant=request.user)
    elif request.user.is_superuser:
        paiements = PaiementScolarite.objects.all()
    elif request.user.role == Utilisateur.Role.PERSONNEL and request.user.entite_id:
        paiements = PaiementScolarite.objects.filter(
            tarif__programme__entite_id=request.user.entite_id
        )
    else:
        raise PermissionDenied

    paiement = get_object_or_404(
        paiements.select_related(
            "etudiant", "tarif__programme__entite", "tarif__periode", "valide_par"
        ),
        pk=paiement_id,
        statut=PaiementScolarite.Statut.VALIDE,
    )
    pdf = generer_recu_paiement_pdf(paiement)
    JournalAction.objects.create(
        utilisateur=request.user,
        action="paiement.recu_pdf_genere",
        type_objet="PaiementScolarite",
        identifiant_objet=str(paiement.pk),
        details={"reference": paiement.reference},
        adresse_ip=request.META.get("REMOTE_ADDR"),
    )
    reponse = HttpResponse(pdf, content_type="application/pdf")
    reference_fichier = slugify(paiement.reference) or "paiement"
    reponse["Content-Disposition"] = (
        f'attachment; filename="recu-{paiement.pk}-{reference_fichier}.pdf"'
    )
    return reponse


def _paiements_autorises(request):
    paiements = PaiementScolarite.objects.select_related(
        "etudiant", "tarif__programme", "tarif__periode"
    )
    if request.user.is_superuser:
        return paiements
    if request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id:
        raise PermissionDenied
    return paiements.filter(tarif__programme__entite_id=request.user.entite_id)


@login_required
def paiements_a_verifier(request):
    paiements = list(
        _paiements_autorises(request).filter(statut=PaiementScolarite.Statut.EN_ATTENTE)
    )
    identifiants_tarifs = {paiement.tarif_id for paiement in paiements}
    totaux_confirmes = {
        (ligne["etudiant_id"], ligne["tarif_id"]): ligne["total"]
        for ligne in PaiementScolarite.objects.filter(
            statut=PaiementScolarite.Statut.VALIDE,
            tarif_id__in=identifiants_tarifs,
        )
        .values("etudiant_id", "tarif_id")
        .annotate(total=Sum("montant"))
    }
    for paiement in paiements:
        paiement.total_deja_confirme = totaux_confirmes.get(
            (paiement.etudiant_id, paiement.tarif_id), 0
        )
        paiement.reste_a_payer = max(
            paiement.tarif.montant - paiement.total_deja_confirme, 0
        )
    return render(
        request,
        "inscriptions/paiements_registrariat.django",
        {"paiements": paiements},
    )


@login_required
@require_POST
def decider_paiement(request, paiement_id):
    if not request.user.is_superuser and (
        request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id
    ):
        raise PermissionDenied

    decision = request.POST.get("decision")
    motif_refus = request.POST.get("motif_refus", "").strip()
    if decision not in {
        PaiementScolarite.Statut.VALIDE,
        PaiementScolarite.Statut.REFUSE,
    }:
        return HttpResponseBadRequest("Decision de paiement invalide.")
    if decision == PaiementScolarite.Statut.REFUSE and not motif_refus:
        messages.error(request, "Un motif est requis pour refuser le paiement.")
        return redirect("inscriptions:paiements_a_verifier")

    with transaction.atomic():
        paiement = get_object_or_404(
            _paiements_autorises(request).select_for_update(), pk=paiement_id
        )
        if paiement.statut != PaiementScolarite.Statut.EN_ATTENTE:
            messages.warning(request, "Ce paiement a deja ete traite.")
            return redirect("inscriptions:paiements_a_verifier")
        if (
            decision == PaiementScolarite.Statut.VALIDE
            and not JournalAction.objects.filter(
                utilisateur=request.user,
                action="dossier.consulte",
                details__etudiant=paiement.etudiant.username,
                details__periode=paiement.tarif.periode.code,
            ).exists()
        ):
            messages.error(
                request,
                "Verifiez d'abord le dossier de cet etudiant pour cette periode.",
            )
            return redirect("inscriptions:paiements_a_verifier")
        paiement.statut = decision
        paiement.valide_par = request.user
        paiement.date_validation = timezone.now()
        paiement.motif_refus = (
            motif_refus if decision == PaiementScolarite.Statut.REFUSE else ""
        )
        paiement.full_clean()
        paiement.save(
            update_fields=("statut", "valide_par", "date_validation", "motif_refus")
        )
        JournalAction.objects.create(
            utilisateur=request.user,
            action=f"paiement.{decision}",
            type_objet="PaiementScolarite",
            identifiant_objet=str(paiement.pk),
            details={"motif": paiement.motif_refus},
            adresse_ip=request.META.get("REMOTE_ADDR"),
        )
    messages.success(request, "La decision a ete enregistree.")
    return redirect("inscriptions:paiements_a_verifier")


@login_required
def inscription_etudiant(request):
    if request.user.role != Utilisateur.Role.ETUDIANT:
        raise PermissionDenied

    if request.method == "POST":
        formulaire = FormulaireInscriptionPedagogique(
            request.POST, utilisateur=request.user
        )
        if formulaire.is_valid():
            programme = formulaire.cleaned_data["programme"]
            periode = formulaire.cleaned_data["periode"]
            tarif = get_object_or_404(
                TarifScolarite,
                programme=programme,
                periode=periode,
                est_actif=True,
            )
            if not frais_scolarite_acquittes(request.user, tarif):
                formulaire.add_error(
                    None,
                    "Les frais doivent etre integralement valides avant l'inscription.",
                )
            else:
                inscription = InscriptionPedagogique(
                    etudiant=request.user,
                    programme=programme,
                    periode=periode,
                )
                try:
                    inscription.full_clean()
                except ValidationError as erreur:
                    formulaire.add_error(None, erreur)
                else:
                    with transaction.atomic():
                        inscription.save()
                        JournalAction.objects.create(
                            utilisateur=request.user,
                            action="inscription.soumise",
                            type_objet="InscriptionPedagogique",
                            identifiant_objet=str(inscription.pk),
                            details={
                                "programme": programme.code,
                                "periode": periode.code,
                            },
                            adresse_ip=request.META.get("REMOTE_ADDR"),
                        )
                    messages.success(
                        request,
                        "Votre demande est en attente de verification par le registrariat.",
                    )
                    return redirect("inscriptions:inscription_etudiant")
    else:
        formulaire = FormulaireInscriptionPedagogique(utilisateur=request.user)

    inscriptions = InscriptionPedagogique.objects.filter(
        etudiant=request.user
    ).select_related("programme", "periode", "traite_par")
    return render(
        request,
        "inscriptions/inscription_etudiant.django",
        {
            "formulaire": formulaire,
            "inscriptions": inscriptions,
            "choix_disponible": formulaire.fields["programme"].queryset.exists(),
        },
    )


def _inscriptions_autorisees(request):
    inscriptions = InscriptionPedagogique.objects.select_related(
        "etudiant", "programme__entite", "periode", "traite_par"
    )
    if request.user.is_superuser:
        return inscriptions
    if request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id:
        raise PermissionDenied
    return inscriptions.filter(programme__entite_id=request.user.entite_id)


def _afficher_erreur_dossier_etudiant(request, titre, message):
    est_etudiant = request.user.role == Utilisateur.Role.ETUDIANT
    return render(
        request,
        "inscriptions/erreur_dossier_etudiant.django",
        {
            "titre": titre,
            "message": message,
            "url_retour": (
                "inscriptions:paiement_etudiant"
                if est_etudiant
                else "inscriptions:inscriptions_a_traiter"
            ),
            "libelle_retour": (
                "Voir mes paiements" if est_etudiant else "Retour aux inscriptions"
            ),
        },
    )


@login_required
def verifier_dossier_etudiant(request):
    if not request.user.is_superuser and (
        request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id
    ):
        raise PermissionDenied

    formulaire = FormulaireRechercheDossier(
        request.POST if request.method == "POST" else None,
        utilisateur=request.user,
    )
    resultat = None
    if request.method == "POST" and formulaire.is_valid():
        identifiant = formulaire.cleaned_data["identifiant"]
        periode = formulaire.cleaned_data["periode"]
        profils = ProfilEtudiant.objects.filter(
            utilisateur__role=Utilisateur.Role.ETUDIANT
        ).filter(
            Q(code_etudiant__iexact=identifiant)
            | Q(nif__iexact=identifiant)
            | Q(cin__iexact=identifiant)
        )
        if not request.user.is_superuser:
            profils = profils.filter(utilisateur__entite_id=request.user.entite_id)

        profils = list(profils.select_related("utilisateur")[:2])
        if not profils:
            formulaire.add_error(
                "identifiant", "Aucun etudiant ne correspond a cet identifiant."
            )
        elif len(profils) > 1:
            formulaire.add_error(
                "identifiant",
                "Cet identifiant correspond a plusieurs dossiers. Utilisez le code etudiant.",
            )
        else:
            profil = profils[0]
            etudiant = profil.utilisateur
            if etudiant.entite_id != periode.entite_id:
                formulaire.add_error(
                    "periode",
                    "La periode choisie doit appartenir a l'entite de l'etudiant.",
                )
            else:
                tarifs = list(
                    TarifScolarite.objects.filter(
                        programme__entite_id=etudiant.entite_id,
                        periode=periode,
                    ).select_related("programme", "periode")
                )
                for tarif in tarifs:
                    paiements = PaiementScolarite.objects.filter(
                        etudiant=etudiant,
                        tarif=tarif,
                    ).order_by("date_paiement", "pk")
                    tarif.total_confirme = montant_scolarite_confirme(etudiant, tarif)
                    tarif.total_en_attente = (
                        paiements.filter(
                            statut=PaiementScolarite.Statut.EN_ATTENTE
                        ).aggregate(total=Sum("montant"))["total"]
                        or 0
                    )
                    tarif.frais_acquittes = tarif.total_confirme >= tarif.montant
                    tarif.paiements_valides = paiements.filter(
                        statut=PaiementScolarite.Statut.VALIDE
                    )

                inscriptions = list(
                    InscriptionPedagogique.objects.filter(
                        etudiant=etudiant,
                        periode=periode,
                    ).select_related("programme", "traite_par")
                )
                from applications.rapports.services import evaluer_inscriptions_passage

                inscriptions = evaluer_inscriptions_passage(inscriptions)
                dossiers = etudiant.dossiers_etudes.filter(
                    programme__entite_id=etudiant.entite_id
                ).select_related("programme")
                resultat = {
                    "profil": profil,
                    "etudiant": etudiant,
                    "periode": periode,
                    "tarifs": tarifs,
                    "inscriptions": inscriptions,
                    "dossiers": dossiers,
                }
                JournalAction.objects.create(
                    utilisateur=request.user,
                    action="dossier.consulte",
                    type_objet="ProfilEtudiant",
                    identifiant_objet=str(profil.pk),
                    details={"etudiant": etudiant.username, "periode": periode.code},
                    adresse_ip=request.META.get("REMOTE_ADDR"),
                )

    return render(
        request,
        "inscriptions/verification_dossier.django",
        {"formulaire": formulaire, "resultat": resultat},
    )


@login_required
def inscriptions_a_traiter(request):
    inscriptions = _inscriptions_autorisees(request).filter(
        statut=InscriptionPedagogique.Statut.EN_ATTENTE
    )
    return render(
        request,
        "inscriptions/inscriptions_registrariat.django",
        {"inscriptions": inscriptions},
    )


@login_required
@require_POST
def decider_inscription(request, inscription_id):
    if not request.user.is_superuser and (
        request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id
    ):
        raise PermissionDenied

    decision = request.POST.get("decision")
    motif = request.POST.get("motif_decision", "").strip()
    if decision not in {
        InscriptionPedagogique.Statut.VALIDEE,
        InscriptionPedagogique.Statut.REFUSEE,
    }:
        return HttpResponseBadRequest("Decision d'inscription invalide.")
    if decision == InscriptionPedagogique.Statut.REFUSEE and not motif:
        messages.error(request, "Un motif est requis pour refuser l'inscription.")
        return redirect("inscriptions:inscriptions_a_traiter")
    if (
        decision == InscriptionPedagogique.Statut.VALIDEE
        and request.POST.get("conditions_passage_verifiees") != "on"
    ):
        messages.error(
            request,
            "Confirmez la verification des conditions de passage avant d'approuver.",
        )
        return redirect("inscriptions:inscriptions_a_traiter")

    with transaction.atomic():
        inscription = get_object_or_404(
            _inscriptions_autorisees(request).select_for_update(), pk=inscription_id
        )
        if inscription.statut != InscriptionPedagogique.Statut.EN_ATTENTE:
            messages.warning(request, "Cette demande a deja ete traitee.")
            return redirect("inscriptions:inscriptions_a_traiter")
        if decision == InscriptionPedagogique.Statut.VALIDEE:
            tarif = get_object_or_404(
                TarifScolarite,
                programme=inscription.programme,
                periode=inscription.periode,
                est_actif=True,
            )
            if not frais_scolarite_acquittes(inscription.etudiant, tarif):
                messages.error(
                    request,
                    "Les frais ne sont pas integralement valides; la demande reste en attente.",
                )
                return redirect("inscriptions:inscriptions_a_traiter")
            inscription.conditions_passage_verifiees = True
        inscription.statut = decision
        inscription.traite_par = request.user
        inscription.date_validation = timezone.now()
        inscription.motif_decision = (
            motif if decision == InscriptionPedagogique.Statut.REFUSEE else ""
        )
        inscription.full_clean()
        inscription.save(
            update_fields=(
                "statut",
                "conditions_passage_verifiees",
                "traite_par",
                "date_validation",
                "motif_decision",
            )
        )
        JournalAction.objects.create(
            utilisateur=request.user,
            action=f"inscription.{decision}",
            type_objet="InscriptionPedagogique",
            identifiant_objet=str(inscription.pk),
            details={"motif": inscription.motif_decision},
            adresse_ip=request.META.get("REMOTE_ADDR"),
        )
    messages.success(request, "La decision a ete enregistree.")
    return redirect("inscriptions:inscriptions_a_traiter")


@login_required
def choix_cours_etudiant(request, inscription_id):
    if request.user.role != Utilisateur.Role.ETUDIANT:
        raise PermissionDenied

    inscription = get_object_or_404(
        InscriptionPedagogique.objects.select_related(
            "programme", "periode", "etudiant"
        ),
        pk=inscription_id,
        etudiant=request.user,
        statut=InscriptionPedagogique.Statut.VALIDEE,
        conditions_passage_verifiees=True,
    )
    tarif = TarifScolarite.objects.filter(
        programme=inscription.programme,
        periode=inscription.periode,
    ).first()
    if tarif is None:
        return _afficher_erreur_dossier_etudiant(
            request,
            "Tarif introuvable",
            "Aucun tarif de scolarite n'est associe a cette inscription. Contactez le Registrariat pour verifier le dossier.",
        )
    if not frais_scolarite_acquittes(request.user, tarif):
        total_confirme = montant_scolarite_confirme(request.user, tarif)
        return _afficher_erreur_dossier_etudiant(
            request,
            "Paiement incomplet",
            f"Les frais de scolarite ne sont pas integralement valides ({total_confirme} {tarif.devise} sur {tarif.montant} {tarif.devise}). Consultez vos paiements ou contactez le Registrariat.",
        )

    if request.method == "POST" and not inscription.periode.est_ouverte:
        messages.error(request, "La periode est fermee aux modifications de cours.")
        return redirect("inscriptions:choix_cours_etudiant", inscription.pk)

    formulaire = FormulaireSelectionCours(
        request.POST if request.method == "POST" else None,
        inscription=inscription,
    )
    if request.method == "POST" and formulaire.is_valid():
        cours_choisis = list(formulaire.cleaned_data["cours"])
        with transaction.atomic():
            inscription = get_object_or_404(
                InscriptionPedagogique.objects.select_for_update(),
                pk=inscription.pk,
                etudiant=request.user,
                statut=InscriptionPedagogique.Statut.VALIDEE,
                conditions_passage_verifiees=True,
            )
            SelectionCours.objects.filter(inscription=inscription).delete()
            SelectionCours.objects.bulk_create(
                [
                    SelectionCours(inscription=inscription, cours=cours)
                    for cours in cours_choisis
                ]
            )
            JournalAction.objects.create(
                utilisateur=request.user,
                action="inscription.cours_modifies",
                type_objet="InscriptionPedagogique",
                identifiant_objet=str(inscription.pk),
                details={"cours": [cours.code for cours in cours_choisis]},
                adresse_ip=request.META.get("REMOTE_ADDR"),
            )
        messages.success(request, "Votre choix de cours a ete enregistre.")
        return redirect("inscriptions:choix_cours_etudiant", inscription.pk)

    return render(
        request,
        "inscriptions/choix_cours_etudiant.django",
        {
            "inscription": inscription,
            "formulaire": formulaire,
            "peut_modifier": inscription.periode.est_ouverte,
            "cours_selectionnes": inscription.cours_selectionnes.select_related(
                "cours"
            ),
        },
    )


@login_required
def imprimer_fiche_inscription(request, inscription_id):
    inscriptions = InscriptionPedagogique.objects.select_related(
        "etudiant", "programme__entite", "periode", "traite_par"
    )
    if request.user.role == Utilisateur.Role.ETUDIANT:
        inscriptions = inscriptions.filter(etudiant=request.user)
    elif request.user.is_superuser:
        pass
    elif request.user.role == Utilisateur.Role.PERSONNEL and request.user.entite_id:
        inscriptions = inscriptions.filter(programme__entite_id=request.user.entite_id)
    else:
        raise PermissionDenied

    inscription = get_object_or_404(
        inscriptions,
        pk=inscription_id,
        statut=InscriptionPedagogique.Statut.VALIDEE,
        conditions_passage_verifiees=True,
    )
    tarif = (
        TarifScolarite.objects.select_related("programme", "periode")
        .filter(
            programme=inscription.programme,
            periode=inscription.periode,
        )
        .first()
    )
    if tarif is None:
        return _afficher_erreur_dossier_etudiant(
            request,
            "Tarif introuvable",
            "Aucun tarif de scolarite n'est associe a cette inscription. Contactez le Registrariat pour faire verifier le dossier.",
        )
    if not frais_scolarite_acquittes(inscription.etudiant, tarif):
        total_confirme = montant_scolarite_confirme(inscription.etudiant, tarif)
        return _afficher_erreur_dossier_etudiant(
            request,
            "Paiement incomplet",
            f"La fiche n'est disponible qu'apres validation de la totalite des frais ({total_confirme} {tarif.devise} sur {tarif.montant} {tarif.devise}). Consultez vos paiements ou contactez le Registrariat.",
        )

    profil = getattr(inscription.etudiant, "profil_etudiant", None)
    selections = inscription.cours_selectionnes.select_related("cours").order_by(
        "cours__code"
    )
    JournalAction.objects.create(
        utilisateur=request.user,
        action="inscription.fiche_imprimee",
        type_objet="InscriptionPedagogique",
        identifiant_objet=str(inscription.pk),
        details={
            "etudiant": inscription.etudiant.username,
            "programme": inscription.programme.code,
            "periode": inscription.periode.code,
        },
        adresse_ip=request.META.get("REMOTE_ADDR"),
    )
    return render(
        request,
        "inscriptions/fiche_inscription.django",
        {
            "inscription": inscription,
            "profil": profil,
            "tarif": tarif,
            "total_confirme": montant_scolarite_confirme(inscription.etudiant, tarif),
            "selections": selections,
        },
    )
