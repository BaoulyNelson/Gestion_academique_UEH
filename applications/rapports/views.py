import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, F, OuterRef, Subquery, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.utils import timezone

from applications.audit.models import JournalAction
from applications.comptes.models import Utilisateur
from applications.inscriptions.models import InscriptionPedagogique, PaiementScolarite
from applications.referentiels.models import Entite

from .documents import (
    generer_pdf_acte,
    generer_pdf_proces_verbal,
    obtenir_resultats_releve,
)
from .forms import (
    FiltresRapport,
    FiltresListeEtudiants,
    FormulaireDossierEtudes,
    FormulaireEmissionActe,
    FormulaireSoutenance,
)
from .models import ActeAcademique, DossierEtudes, SoutenanceMemoire
from .services import (
    calculer_indicateurs,
    calculer_statistiques_cours,
    evaluer_inscriptions_passage,
)


def _entite_autorisee(request):
    if request.user.is_superuser:
        return None
    if request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id:
        raise PermissionDenied
    return Entite.objects.get(pk=request.user.entite_id)


def _contexte_rapport(request):
    entite_fixe = _entite_autorisee(request)
    formulaire = FiltresRapport(request.GET, utilisateur=request.user)
    formulaire.is_valid()
    entite = entite_fixe or formulaire.cleaned_data.get("entite")
    periode = formulaire.cleaned_data.get("periode")
    programme = formulaire.cleaned_data.get("programme")
    indicateurs = calculer_indicateurs(entite, periode, programme) if entite else None
    statistiques_cours = (
        calculer_statistiques_cours(entite, periode, programme) if entite else []
    )
    return {
        "formulaire": formulaire,
        "entite": entite,
        "periode": periode,
        "programme": programme,
        "indicateurs": indicateurs,
        "statistiques_cours": statistiques_cours,
    }


@login_required
def tableau_rapports(request):
    return render(
        request,
        "rapports/tableau_rapports.django",
        _contexte_rapport(request),
    )


@login_required
def liste_etudiants(request):
    entite_fixe = _entite_autorisee(request)
    formulaire = FiltresListeEtudiants(request.GET, utilisateur=request.user)
    formulaire.is_valid()
    entite = entite_fixe or formulaire.cleaned_data.get("entite")
    inscriptions = InscriptionPedagogique.objects.none()
    if entite:
        donnees = formulaire.cleaned_data
        inscriptions = (
            InscriptionPedagogique.objects.filter(programme__entite=entite)
            .select_related(
                "etudiant", "etudiant__profil_etudiant", "programme", "periode"
            )
            .prefetch_related("cours_selectionnes__cours")
            .annotate(
                statut_dossier=Subquery(
                    DossierEtudes.objects.filter(
                        etudiant_id=OuterRef("etudiant_id"),
                        programme_id=OuterRef("programme_id"),
                    ).values("statut")[:1]
                )
            )
        )
        if donnees.get("periode"):
            inscriptions = inscriptions.filter(periode=donnees["periode"])
        if donnees.get("niveau"):
            inscriptions = inscriptions.filter(periode=donnees["niveau"])
        if donnees.get("programme"):
            inscriptions = inscriptions.filter(programme=donnees["programme"])
        if donnees.get("cours"):
            inscriptions = inscriptions.filter(
                cours_selectionnes__cours=donnees["cours"]
            )
        if donnees.get("statut"):
            inscriptions = inscriptions.filter(statut=donnees["statut"])
        if donnees.get("statut_dossier"):
            inscriptions = inscriptions.filter(
                etudiant__dossiers_etudes__programme_id=F("programme_id"),
                etudiant__dossiers_etudes__statut=donnees["statut_dossier"],
            )
        inscriptions = list(
            inscriptions.distinct().order_by(
                "programme__nom",
                "periode__annee_academique",
                "etudiant__last_name",
                "etudiant__first_name",
            )
        )
        inscriptions = evaluer_inscriptions_passage(inscriptions)
        if donnees.get("statut_passage"):
            inscriptions = [
                inscription
                for inscription in inscriptions
                if inscription.statut_passage == donnees["statut_passage"]
            ]
        libelles_statuts_dossiers = dict(DossierEtudes.Statut.choices)
        for inscription in inscriptions:
            inscription.statut_dossier_display = libelles_statuts_dossiers.get(
                inscription.statut_dossier, "Aucun dossier"
            )
    return render(
        request,
        "rapports/liste_etudiants.django",
        {"formulaire": formulaire, "inscriptions": inscriptions, "entite": entite},
    )


@login_required
def liste_paiements_acquittes(request):
    entite_fixe = _entite_autorisee(request)
    formulaire = FiltresRapport(request.GET, utilisateur=request.user)
    formulaire.is_valid()
    donnees = formulaire.cleaned_data
    entite = entite_fixe or donnees.get("entite")
    paiements = PaiementScolarite.objects.none()
    if entite:
        paiements = PaiementScolarite.objects.filter(
            statut=PaiementScolarite.Statut.VALIDE,
            tarif__programme__entite=entite,
        )
        if donnees.get("periode"):
            paiements = paiements.filter(tarif__periode=donnees["periode"])
        if donnees.get("programme"):
            paiements = paiements.filter(tarif__programme=donnees["programme"])
        paiements = list(
            paiements.values(
                "etudiant__profil_etudiant__code_etudiant",
                "etudiant__username",
                "etudiant__first_name",
                "etudiant__last_name",
                "tarif__programme__nom",
                "tarif__periode__nom",
                "tarif__periode__annee_academique",
                "tarif__montant",
                "tarif__devise",
            )
            .annotate(
                total_confirme=Sum("montant"),
                nombre_versements=Count("pk"),
            )
            .filter(total_confirme__gte=F("tarif__montant"))
            .order_by(
                "tarif__programme__nom",
                "tarif__periode__annee_academique",
                "etudiant__last_name",
                "etudiant__first_name",
            )
        )
    return render(
        request,
        "rapports/liste_paiements_acquittes.django",
        {"formulaire": formulaire, "paiements": paiements, "entite": entite},
    )


@login_required
def gestion_dossiers(request, dossier_id=None):
    if not request.user.is_superuser and (
        request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id
    ):
        raise PermissionDenied

    dossier = None
    if dossier_id is not None:
        dossiers = DossierEtudes.objects.select_related(
            "etudiant", "programme", "cree_par"
        )
        if not request.user.is_superuser:
            dossiers = dossiers.filter(programme__entite_id=request.user.entite_id)
        dossier = get_object_or_404(dossiers, pk=dossier_id)

    if request.method == "POST":
        formulaire = FormulaireDossierEtudes(
            request.POST,
            utilisateur=request.user,
            instance=dossier,
        )
        if formulaire.is_valid():
            objet = formulaire.save(commit=False)
            est_nouveau = objet.pk is None
            if est_nouveau:
                objet.cree_par = request.user
            try:
                objet.full_clean()
            except ValidationError as erreur:
                formulaire.add_error(None, erreur)
            else:
                objet.save()
                JournalAction.objects.create(
                    utilisateur=request.user,
                    action="dossier.cree" if est_nouveau else "dossier.modifie",
                    type_objet="DossierEtudes",
                    identifiant_objet=str(objet.pk),
                    details={
                        "etudiant": objet.etudiant.username,
                        "programme": objet.programme.code,
                        "statut": objet.statut,
                    },
                    adresse_ip=request.META.get("REMOTE_ADDR"),
                )
                messages.success(request, "Le dossier d'etudes a ete enregistre.")
                return redirect("rapports:gestion_dossiers")
    else:
        formulaire = FormulaireDossierEtudes(
            utilisateur=request.user,
            instance=dossier,
            initial={"date_ouverture": timezone.localdate()},
        )

    dossiers = DossierEtudes.objects.select_related("etudiant", "programme")
    if not request.user.is_superuser:
        dossiers = dossiers.filter(programme__entite_id=request.user.entite_id)
    return render(
        request,
        "rapports/gestion_dossiers.django",
        {
            "formulaire": formulaire,
            "dossiers": dossiers,
            "dossier_modifie": dossier,
        },
    )


@login_required
def exporter_rapports_csv(request):
    contexte = _contexte_rapport(request)
    indicateurs = contexte["indicateurs"]
    if indicateurs is None:
        raise PermissionDenied

    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse.write("\ufeff")
    reponse["Content-Disposition"] = 'attachment; filename="rapports_gp7.csv"'
    redacteur = csv.writer(reponse)
    redacteur.writerow(("Indicateur", "Valeur"))
    for cle, libelle in (
        ("nombre_etudiants", "Etudiants"),
        ("nombre_profils_renseignes", "Profils renseignes"),
        ("nombre_sexe_non_renseigne", "Sexe non renseigne"),
        ("nombre_inscriptions", "Inscriptions"),
        ("nombre_inscriptions_en_attente", "Inscriptions en attente"),
        ("nombre_inscriptions_validees", "Inscriptions validees"),
        ("nombre_dossiers", "Dossiers d'etudes"),
        ("dossiers_en_cours", "Dossiers en cours"),
        ("dossiers_fermes", "Dossiers fermes"),
        ("abandons", "Abandons"),
        ("nombre_actes", "Actes delivres"),
        ("nombre_diplomes", "Diplomes"),
        ("nombre_attestations_certificats", "Attestations et certificats"),
        ("nombre_soutenances", "Memoires soutenus"),
    ):
        redacteur.writerow((libelle, indicateurs[cle]))
    for ligne in indicateurs["repartition_sexe"]:
        redacteur.writerow((f"Etudiants - {ligne['sexe_display']}", ligne["nombre"]))
    for ligne in indicateurs["repartition_dossiers_sexe"]:
        redacteur.writerow(
            (
                f"Dossiers - {ligne['statut_display']} - {ligne['sexe_display']}",
                ligne["nombre"],
            )
        )
    for ligne in indicateurs["repartition_actes_sexe"]:
        redacteur.writerow(
            (
                f"Actes - {ligne['type_acte_display']} - {ligne['sexe_display']}",
                ligne["nombre"],
            )
        )
    for ligne in indicateurs["repartition_soutenances_sexe"]:
        redacteur.writerow(
            (f"Memoires soutenus - {ligne['sexe_display']}", ligne["nombre"])
        )
    redacteur.writerow(("Statistiques par cours", ""))
    for resultat in contexte["statistiques_cours"]:
        libelle_cours = (
            f"{resultat['cours'].code} - {resultat['cours'].nom}"
            f" - {resultat['periode'].nom}"
        )
        if resultat["seuil_reussite"] is None:
            redacteur.writerow(
                (
                    libelle_cours,
                    f"Non configure ({resultat['nombre_etudiants']} etudiants)",
                )
            )
            continue
        redacteur.writerow(
            (
                f"{libelle_cours} - Reussites (seuil {resultat['seuil_reussite']})",
                resultat["reussites"],
            )
        )
        redacteur.writerow(
            (
                f"{libelle_cours} - Reprises (seuil {resultat['seuil_reprise']})",
                resultat["reprises"],
            )
        )
        redacteur.writerow((f"{libelle_cours} - Echecs", resultat["echecs"]))
        for ligne in resultat["repartition_sexe"]:
            redacteur.writerow(
                (
                    f"{libelle_cours} - {ligne['sexe_display']}",
                    f"{ligne['reussites']} reussites / {ligne['reprises']} reprises"
                    f" / {ligne['echecs']} echecs",
                )
            )
    return reponse


@login_required
def actes_etudiant(request):
    if request.user.role != Utilisateur.Role.ETUDIANT:
        raise PermissionDenied
    actes = ActeAcademique.objects.filter(
        etudiant=request.user,
        est_annule=False,
    ).select_related("programme", "periode")
    return render(request, "rapports/actes_etudiant.django", {"actes": actes})


@login_required
def gestion_actes(request):
    if not request.user.is_superuser and (
        request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id
    ):
        raise PermissionDenied

    if request.method == "POST":
        formulaire = FormulaireEmissionActe(request.POST, utilisateur=request.user)
        if formulaire.is_valid():
            acte = formulaire.save(commit=False)
            acte.delivre_par = request.user
            try:
                acte.full_clean()
            except ValidationError as erreur:
                formulaire.add_error(None, erreur)
            else:
                acte.save()
                JournalAction.objects.create(
                    utilisateur=request.user,
                    action="acte.delivre",
                    type_objet="ActeAcademique",
                    identifiant_objet=str(acte.pk),
                    details={"reference": acte.reference, "type_acte": acte.type_acte},
                    adresse_ip=request.META.get("REMOTE_ADDR"),
                )
                messages.success(request, "L'acte a ete emis et journalise.")
                return redirect("rapports:gestion_actes")
    else:
        formulaire = FormulaireEmissionActe(
            utilisateur=request.user,
            initial={"date_delivrance": timezone.localdate()},
        )

    actes = ActeAcademique.objects.select_related("etudiant", "programme", "periode")
    if not request.user.is_superuser:
        actes = actes.filter(programme__entite_id=request.user.entite_id)
    return render(
        request,
        "rapports/gestion_actes.django",
        {"formulaire": formulaire, "actes": actes},
    )


@login_required
def acte_imprimable(request, acte_id):
    actes = ActeAcademique.objects.select_related(
        "programme", "periode", "etudiant", "delivre_par"
    ).filter(est_annule=False)
    if request.user.role == Utilisateur.Role.ETUDIANT:
        actes = actes.filter(etudiant=request.user)
        retour_url = "rapports:actes_etudiant"
    else:
        entite = _entite_autorisee(request)
        if entite:
            actes = actes.filter(programme__entite=entite)
        retour_url = "rapports:gestion_actes"
    acte = get_object_or_404(actes, pk=acte_id)
    resultats = (
        obtenir_resultats_releve(acte)
        if acte.type_acte == ActeAcademique.TypeActe.RELEVE_NOTES
        else []
    )
    return render(
        request,
        "rapports/acte_imprimable.django",
        {"acte": acte, "resultats": resultats, "retour_url": retour_url},
    )


@login_required
def telecharger_acte_pdf(request, acte_id):
    actes = ActeAcademique.objects.select_related(
        "programme__entite", "periode", "etudiant", "delivre_par"
    ).filter(est_annule=False)
    if request.user.role == Utilisateur.Role.ETUDIANT:
        actes = actes.filter(etudiant=request.user)
    else:
        entite = _entite_autorisee(request)
        if entite:
            actes = actes.filter(programme__entite=entite)
    acte = get_object_or_404(actes, pk=acte_id)
    pdf = generer_pdf_acte(acte)
    JournalAction.objects.create(
        utilisateur=request.user,
        action="acte.pdf_genere",
        type_objet="ActeAcademique",
        identifiant_objet=str(acte.pk),
        details={"reference": acte.reference, "type_acte": acte.type_acte},
        adresse_ip=request.META.get("REMOTE_ADDR"),
    )
    nom_fichier = slugify(acte.reference) or f"acte-{acte.pk}"
    reponse = HttpResponse(pdf, content_type="application/pdf")
    reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}.pdf"'
    return reponse


@login_required
def proces_verbaux_soutenances(request):
    soutenances = SoutenanceMemoire.objects.filter(
        statut=SoutenanceMemoire.Statut.SOUTENUE
    ).select_related("etudiant", "programme", "periode")
    formulaire = None

    if request.user.role == Utilisateur.Role.ETUDIANT:
        soutenances = soutenances.filter(etudiant=request.user)
    else:
        entite_fixe = _entite_autorisee(request)
        formulaire = FiltresRapport(request.GET, utilisateur=request.user)
        formulaire.is_valid()
        entite = entite_fixe or formulaire.cleaned_data.get("entite")
        periode = formulaire.cleaned_data.get("periode")
        programme = formulaire.cleaned_data.get("programme")
        if entite:
            soutenances = soutenances.filter(programme__entite=entite)
            if periode:
                soutenances = soutenances.filter(periode=periode)
            if programme:
                soutenances = soutenances.filter(programme=programme)
        else:
            soutenances = soutenances.none()

    return render(
        request,
        "rapports/proces_verbaux_soutenances.django",
        {"soutenances": soutenances, "formulaire": formulaire},
    )


@login_required
def gestion_soutenances(request, soutenance_id=None):
    if not request.user.is_superuser and (
        request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id
    ):
        raise PermissionDenied

    soutenance = None
    if soutenance_id is not None:
        soutenances = SoutenanceMemoire.objects.select_related(
            "programme", "etudiant", "periode"
        )
        if not request.user.is_superuser:
            soutenances = soutenances.filter(
                programme__entite_id=request.user.entite_id
            )
        soutenance = get_object_or_404(soutenances, pk=soutenance_id)

    if request.method == "POST":
        formulaire = FormulaireSoutenance(
            request.POST,
            utilisateur=request.user,
            instance=soutenance,
        )
        if formulaire.is_valid():
            objet = formulaire.save(commit=False)
            est_nouvelle = objet.pk is None
            if est_nouvelle:
                objet.enregistre_par = request.user
            try:
                objet.full_clean()
            except ValidationError as erreur:
                formulaire.add_error(None, erreur)
            else:
                objet.save()
                JournalAction.objects.create(
                    utilisateur=request.user,
                    action=(
                        "soutenance.planifiee"
                        if est_nouvelle
                        else "soutenance.modifiee"
                    ),
                    type_objet="SoutenanceMemoire",
                    identifiant_objet=str(objet.pk),
                    details={
                        "etudiant": objet.etudiant.username,
                        "programme": objet.programme.code,
                        "periode": objet.periode.code,
                        "statut": objet.statut,
                    },
                    adresse_ip=request.META.get("REMOTE_ADDR"),
                )
                messages.success(request, "La soutenance a ete enregistree.")
                return redirect("rapports:gestion_soutenances")
    else:
        formulaire = FormulaireSoutenance(
            utilisateur=request.user,
            instance=soutenance,
        )

    soutenances = SoutenanceMemoire.objects.select_related(
        "etudiant", "programme", "periode"
    )
    if not request.user.is_superuser:
        soutenances = soutenances.filter(programme__entite_id=request.user.entite_id)
    return render(
        request,
        "rapports/gestion_soutenances.django",
        {
            "formulaire": formulaire,
            "soutenances": soutenances,
            "soutenance_modifiee": soutenance,
        },
    )


@login_required
def proces_verbal_soutenance_imprimable(request, soutenance_id):
    soutenances = SoutenanceMemoire.objects.filter(
        statut=SoutenanceMemoire.Statut.SOUTENUE
    ).select_related("etudiant", "programme__entite", "periode", "enregistre_par")
    if request.user.role == Utilisateur.Role.ETUDIANT:
        soutenances = soutenances.filter(etudiant=request.user)
    else:
        entite = _entite_autorisee(request)
        if entite:
            soutenances = soutenances.filter(programme__entite=entite)
    soutenance = get_object_or_404(soutenances, pk=soutenance_id)
    return render(
        request,
        "rapports/proces_verbal_soutenance_imprimable.django",
        {"soutenance": soutenance},
    )


@login_required
def telecharger_proces_verbal_pdf(request, soutenance_id):
    soutenances = SoutenanceMemoire.objects.filter(
        statut=SoutenanceMemoire.Statut.SOUTENUE
    ).select_related("etudiant", "programme__entite", "periode", "enregistre_par")
    if request.user.role == Utilisateur.Role.ETUDIANT:
        soutenances = soutenances.filter(etudiant=request.user)
    else:
        entite = _entite_autorisee(request)
        if entite:
            soutenances = soutenances.filter(programme__entite=entite)
    soutenance = get_object_or_404(soutenances, pk=soutenance_id)
    pdf = generer_pdf_proces_verbal(soutenance)
    JournalAction.objects.create(
        utilisateur=request.user,
        action="soutenance.pdf_genere",
        type_objet="SoutenanceMemoire",
        identifiant_objet=str(soutenance.pk),
        details={
            "programme": soutenance.programme.code,
            "periode": soutenance.periode.code,
        },
        adresse_ip=request.META.get("REMOTE_ADDR"),
    )
    nom_fichier = slugify(soutenance.titre) or f"soutenance-{soutenance.pk}"
    reponse = HttpResponse(pdf, content_type="application/pdf")
    reponse["Content-Disposition"] = f'attachment; filename="pv-{nom_fichier}.pdf"'
    return reponse
