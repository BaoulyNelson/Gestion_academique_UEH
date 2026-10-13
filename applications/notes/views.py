from collections import defaultdict
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from applications.audit.models import JournalAction
from applications.comptes.models import ProfilEtudiant, Utilisateur
from applications.inscriptions.models import InscriptionPedagogique
from applications.referentiels.models import AffectationCours, Cours, PeriodeAcademique

from .forms import (
    FormulaireConsultationResultats,
    FormulaireEvaluation,
    FormulaireImportEvaluations,
    FormulaireListeEvaluations,
)
from .forms import FormulaireProgrammationExamen
from .models import Evaluation, ProgrammationExamen
from .services.import_excel import lire_evaluations_excel
from .services.resultats import (
    calculer_moyenne_ponderee,
    calculer_moyennes_academiques,
    mention_pour_moyenne,
)


@login_required
def saisir_evaluation(request, cours_id, periode_id):
    if request.user.role != Utilisateur.Role.PROFESSEUR:
        raise PermissionDenied

    affectation = get_object_or_404(
        AffectationCours.objects.select_related("cours", "periode"),
        professeur=request.user,
        cours_id=cours_id,
        periode_id=periode_id,
    )
    cours = affectation.cours
    periode = affectation.periode
    erreurs = []

    if request.method == "POST":
        formulaire = FormulaireEvaluation(request.POST, cours=cours, periode=periode)
        if formulaire.is_valid():
            etudiant = formulaire.cleaned_data["etudiant"]
            libelle = formulaire.cleaned_data["libelle"].strip()
            with transaction.atomic():
                evaluation = (
                    Evaluation.objects.select_for_update()
                    .filter(
                        etudiant=etudiant,
                        cours=cours,
                        periode=periode,
                        libelle=libelle,
                    )
                    .first()
                )
                if evaluation and evaluation.est_publiee:
                    formulaire.add_error(
                        None,
                        "Cette note est publiee; le registrariat doit la retirer de publication avant modification.",
                    )
                else:
                    evaluation = evaluation or Evaluation(
                        etudiant=etudiant,
                        cours=cours,
                        periode=periode,
                        libelle=libelle,
                    )
                    evaluation.etudiant = etudiant
                    evaluation.cours = cours
                    evaluation.periode = periode
                    evaluation.libelle = libelle
                    evaluation.note = formulaire.cleaned_data["note"]
                    evaluation.coefficient = formulaire.cleaned_data["coefficient"]
                    evaluation.saisie_par = request.user
                    try:
                        evaluation.full_clean()
                    except ValidationError as erreur:
                        formulaire.add_error(None, erreur)
                    else:
                        evaluation.save()
                        JournalAction.objects.create(
                            utilisateur=request.user,
                            action="note.saisiee",
                            type_objet="Evaluation",
                            identifiant_objet=str(evaluation.pk),
                            details={
                                "cours": cours.code,
                                "periode": periode.code,
                                "etudiant": etudiant.username,
                                "libelle": libelle,
                            },
                            adresse_ip=request.META.get("REMOTE_ADDR"),
                        )
                        messages.success(request, "La note a ete enregistree.")
                        return redirect("notes:saisir_evaluation", cours.pk, periode.pk)
    else:
        formulaire = FormulaireEvaluation(cours=cours, periode=periode)

    evaluations = Evaluation.objects.filter(
        cours=cours, periode=periode
    ).select_related("etudiant", "saisie_par")
    for evaluation in evaluations:
        evaluation.moyenne_cours = calculer_moyenne_ponderee(
            Evaluation.objects.filter(
                etudiant=evaluation.etudiant,
                cours=cours,
                periode=periode,
            )
        )

    return render(
        request,
        "notes/saisie_evaluation.django",
        {
            "cours": cours,
            "periode": periode,
            "formulaire": formulaire,
            "evaluations": evaluations,
            "erreurs": erreurs,
        },
    )


@login_required
@require_POST
def importer_evaluations_excel(request, cours_id, periode_id):
    if request.user.role != Utilisateur.Role.PROFESSEUR:
        raise PermissionDenied

    affectation = get_object_or_404(
        AffectationCours.objects.select_related("cours", "periode"),
        professeur=request.user,
        cours_id=cours_id,
        periode_id=periode_id,
    )
    formulaire = FormulaireImportEvaluations(request.POST, request.FILES)
    if not formulaire.is_valid():
        for erreur in formulaire.errors.get("fichier", []):
            messages.error(request, erreur)
        return redirect("notes:saisir_evaluation", cours_id, periode_id)

    try:
        lignes = lire_evaluations_excel(formulaire.cleaned_data["fichier"])
    except ValidationError as erreur:
        for message in erreur.messages:
            messages.error(request, message)
        return redirect("notes:saisir_evaluation", cours_id, periode_id)

    etudiants_inscrits = (
        FormulaireEvaluation(cours=affectation.cours, periode=affectation.periode)
        .fields["etudiant"]
        .queryset
    )
    etudiants_par_code = {
        profil.code_etudiant: profil.utilisateur
        for profil in ProfilEtudiant.objects.filter(utilisateur__in=etudiants_inscrits)
        .exclude(code_etudiant__isnull=True)
        .exclude(code_etudiant="")
        .select_related("utilisateur")
    }
    erreurs = []
    candidats = []
    cles_vues = set()

    with transaction.atomic():
        for ligne in lignes:
            etudiant = etudiants_par_code.get(ligne["code_etudiant"])
            if etudiant is None:
                erreurs.append(
                    f"Ligne {ligne['ligne']}: code etudiant inconnu ou non inscrit a ce cours."
                )
                continue
            cle = (etudiant.pk, ligne["libelle"])
            if cle in cles_vues:
                erreurs.append(
                    f"Ligne {ligne['ligne']}: cette evaluation est repetee pour le meme etudiant."
                )
                continue
            cles_vues.add(cle)
            candidats.append((ligne, etudiant))

        evaluations_existantes = {
            (evaluation.etudiant_id, evaluation.libelle): evaluation
            for evaluation in Evaluation.objects.select_for_update().filter(
                cours=affectation.cours,
                periode=affectation.periode,
                etudiant_id__in=[etudiant.pk for _, etudiant in candidats],
                libelle__in=[ligne["libelle"] for ligne, _ in candidats],
            )
        }
        objets = []
        for ligne, etudiant in candidats:
            evaluation = evaluations_existantes.get((etudiant.pk, ligne["libelle"]))
            if evaluation and evaluation.est_publiee:
                erreurs.append(
                    f"Ligne {ligne['ligne']}: la note publiee doit etre retiree de publication avant modification."
                )
                continue
            evaluation = evaluation or Evaluation(
                etudiant=etudiant,
                cours=affectation.cours,
                periode=affectation.periode,
                libelle=ligne["libelle"],
            )
            evaluation.note = ligne["note"]
            evaluation.coefficient = ligne["coefficient"]
            evaluation.saisie_par = request.user
            try:
                evaluation.full_clean()
            except ValidationError as erreur:
                erreurs.append(f"Ligne {ligne['ligne']}: {'; '.join(erreur.messages)}")
                continue
            objets.append(evaluation)

        if not erreurs:
            for evaluation in objets:
                evaluation.save()
            JournalAction.objects.create(
                utilisateur=request.user,
                action="notes.importees",
                type_objet="Evaluation",
                identifiant_objet=f"cours:{cours_id}:periode:{periode_id}",
                details={"nombre": len(objets)},
                adresse_ip=request.META.get("REMOTE_ADDR"),
            )

    if erreurs:
        for erreur in erreurs:
            messages.error(request, erreur)
    else:
        messages.success(request, f"{len(objets)} notes ont ete importees.")
    return redirect("notes:saisir_evaluation", cours_id, periode_id)


def _evaluations_autorisees(request):
    evaluations = Evaluation.objects.select_related(
        "etudiant", "cours__programme__entite", "periode"
    )
    if request.user.is_superuser:
        return evaluations
    if request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id:
        raise PermissionDenied
    return evaluations.filter(cours__programme__entite_id=request.user.entite_id)


@login_required
def notes_a_publier(request):
    evaluations = _evaluations_autorisees(request).select_related(
        "cours__programme__entite", "periode", "etudiant"
    )

    def grouper(queryset):
        groupes = {}
        for evaluation in queryset.order_by(
            "cours__code", "periode__annee_academique", "etudiant__last_name"
        ):
            cle = (evaluation.cours_id, evaluation.periode_id)
            if cle not in groupes:
                groupes[cle] = {
                    "cours": evaluation.cours,
                    "periode": evaluation.periode,
                    "evaluations": [],
                }
            groupes[cle]["evaluations"].append(evaluation)
        return list(groupes.values())

    return render(
        request,
        "notes/notes_a_publier.django",
        {
            "groupes": grouper(evaluations.filter(est_publiee=False)),
            "groupes_publies": grouper(evaluations.filter(est_publiee=True)),
        },
    )


@login_required
def liste_evaluations(request):
    if not request.user.is_superuser and (
        request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id
    ):
        raise PermissionDenied

    formulaire = FormulaireListeEvaluations(request.GET, utilisateur=request.user)
    evaluations = []
    resultats = []
    moyennes = {"cours": [], "programmes": [], "periodes": []}
    donnees = (
        formulaire.cleaned_data if formulaire.is_bound and formulaire.is_valid() else {}
    )
    programme = donnees.get("programme")
    periode = donnees.get("periode")
    if programme and periode:
        queryset = _evaluations_autorisees(request).filter(
            cours__programme=programme,
            periode=periode,
        )
        if donnees.get("cours"):
            queryset = queryset.filter(cours__in=donnees["cours"])
        evaluations = list(
            queryset.select_related(
                "etudiant__profil_etudiant", "cours__programme", "periode"
            ).order_by("cours__code", "etudiant__last_name", "libelle")
        )
        groupes = defaultdict(list)
        for evaluation in evaluations:
            groupes[
                (evaluation.etudiant_id, evaluation.cours_id, evaluation.periode_id)
            ].append(evaluation)
        for evaluations_cours in groupes.values():
            premiere = evaluations_cours[0]
            resultats.append(
                {
                    "etudiant": premiere.etudiant,
                    "cours": premiere.cours,
                    "periode": premiere.periode,
                    "evaluations": evaluations_cours,
                    "moyenne": calculer_moyenne_ponderee(
                        [
                            evaluation
                            for evaluation in evaluations_cours
                            if evaluation.est_publiee
                        ]
                    ),
                }
            )
        moyennes = calculer_moyennes_academiques(
            [evaluation for evaluation in evaluations if evaluation.est_publiee]
        )
        for ligne in moyennes["programmes"]:
            ligne["mention"] = mention_pour_moyenne(ligne["periode"], ligne["moyenne"])

    return render(
        request,
        "notes/liste_evaluations.django",
        {
            "formulaire": formulaire,
            "resultats": resultats,
            "moyennes": moyennes,
            "recherche_effectuee": bool(programme and periode),
        },
    )


@login_required
@require_POST
def retirer_publication_note(request, evaluation_id):
    with transaction.atomic():
        evaluation = get_object_or_404(
            _evaluations_autorisees(request)
            .select_for_update()
            .select_related("cours", "periode", "etudiant"),
            pk=evaluation_id,
            est_publiee=True,
        )
        Evaluation.objects.filter(pk=evaluation.pk).update(
            est_publiee=False,
            date_modification=timezone.now(),
        )
        JournalAction.objects.create(
            utilisateur=request.user,
            action="note.publication_retiree",
            type_objet="Evaluation",
            identifiant_objet=str(evaluation.pk),
            details={
                "cours": evaluation.cours.code,
                "periode": evaluation.periode.code,
                "etudiant": evaluation.etudiant.username,
                "libelle": evaluation.libelle,
            },
            adresse_ip=request.META.get("REMOTE_ADDR"),
        )
    messages.success(
        request,
        "La publication a ete retiree. Le professeur peut maintenant corriger cette note.",
    )
    return redirect("notes:notes_a_publier")


@login_required
@require_POST
def publier_notes_cours(request, cours_id, periode_id):
    if not request.user.is_superuser and (
        request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id
    ):
        raise PermissionDenied

    with transaction.atomic():
        evaluations = (
            _evaluations_autorisees(request)
            .select_for_update()
            .filter(
                cours_id=cours_id,
                periode_id=periode_id,
                est_publiee=False,
            )
        )
        identifiants = list(evaluations.values_list("pk", flat=True))
        if not identifiants:
            messages.warning(
                request, "Aucune note en attente pour ce cours et cette periode."
            )
            return redirect("notes:notes_a_publier")
        Evaluation.objects.filter(pk__in=identifiants).update(
            est_publiee=True,
            date_modification=timezone.now(),
        )
        JournalAction.objects.create(
            utilisateur=request.user,
            action="notes.publiees",
            type_objet="Evaluation",
            identifiant_objet=f"cours:{cours_id}:periode:{periode_id}",
            details={"nombre": len(identifiants)},
            adresse_ip=request.META.get("REMOTE_ADDR"),
        )
    messages.success(request, f"{len(identifiants)} notes ont ete publiees.")
    return redirect("notes:notes_a_publier")


@login_required
def resultats_etudiant(request):
    if request.user.role != Utilisateur.Role.ETUDIANT:
        raise PermissionDenied

    formulaire = FormulaireConsultationResultats(
        request.GET, utilisateur=request.user, etudiant=request.user
    )
    resultats, periode_precedente = [], None
    if formulaire.is_valid():
        periode_reference = formulaire.cleaned_data.get("periode_reference")
        if periode_reference:
            periode_precedente = _periode_precedente(periode_reference)
        if not periode_reference:
            resultats = _resultats_publies(
                request.user,
                periode=None,
                programme=formulaire.cleaned_data.get("programme"),
            )
        elif periode_precedente:
            resultats = _resultats_publies(
                request.user,
                periode_precedente,
                formulaire.cleaned_data.get("programme"),
            )
    return render(
        request,
        "notes/resultats_etudiant.django",
        {
            "formulaire": formulaire,
            "resultats": resultats,
            "periode_precedente": periode_precedente,
        },
    )


def _periode_precedente(periode_reference):
    periodes = list(
        PeriodeAcademique.objects.filter(
            entite=periode_reference.entite,
            type_periode=periode_reference.type_periode,
        )
    )
    periodes.sort(
        key=lambda periode: (
            periode.date_debut or date.min,
            periode.annee_academique,
            periode.pk,
        )
    )
    index = next(
        (
            index
            for index, periode in enumerate(periodes)
            if periode.pk == periode_reference.pk
        ),
        None,
    )
    if index is None or index == 0:
        return None
    return periodes[index - 1]


def _resultats_publies(etudiant, periode=None, programme=None):
    evaluations_queryset = Evaluation.objects.filter(est_publiee=True)
    if etudiant:
        evaluations_queryset = evaluations_queryset.filter(etudiant=etudiant)
    if periode:
        evaluations_queryset = evaluations_queryset.filter(periode=periode)
    if programme:
        evaluations_queryset = evaluations_queryset.filter(cours__programme=programme)
    evaluations = list(
        evaluations_queryset.select_related("cours", "cours__programme", "periode")
        .select_related("etudiant")
        .order_by("cours__code", "etudiant__last_name", "libelle")
    )
    groupes = defaultdict(list)
    for evaluation in evaluations:
        groupes[
            (evaluation.cours_id, evaluation.periode_id, evaluation.etudiant_id)
        ].append(evaluation)

    resultats = []
    for evaluations_cours in groupes.values():
        premiere = evaluations_cours[0]
        resultats.append(
            {
                "cours": premiere.cours,
                "periode": premiere.periode,
                "etudiant": premiere.etudiant,
                "evaluations": evaluations_cours,
                "moyenne": calculer_moyenne_ponderee(evaluations_cours),
            }
        )
    return resultats


@login_required
def releves_etudiants(request):
    if not request.user.is_superuser and (
        request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id
    ):
        raise PermissionDenied

    formulaire = FormulaireConsultationResultats(request.GET, utilisateur=request.user)
    resultats, periode_precedente = [], None
    etudiant = None
    if formulaire.is_valid():
        etudiant = formulaire.cleaned_data.get("etudiant")
        periode_reference = formulaire.cleaned_data.get("periode_reference")
        if periode_reference:
            periode_precedente = _periode_precedente(periode_reference)
        if periode_precedente:
            resultats = _resultats_publies(
                etudiant=etudiant,
                periode=periode_precedente,
                programme=formulaire.cleaned_data.get("programme"),
            )
    programme = (
        formulaire.cleaned_data.get("programme") if formulaire.is_valid() else None
    )
    return render(
        request,
        "notes/resultats_etudiant.django",
        {
            "formulaire": formulaire,
            "resultats": resultats,
            "periode_precedente": periode_precedente,
            "etudiant_consulte": etudiant,
            "programme_consulte": programme,
        },
    )


def _examens_visibles(request):
    examens = ProgrammationExamen.objects.select_related(
        "cours__programme__entite", "periode", "planifie_par"
    )
    if request.user.is_superuser:
        return examens
    if request.user.role == Utilisateur.Role.PERSONNEL and request.user.entite_id:
        return examens.filter(cours__programme__entite_id=request.user.entite_id)
    if request.user.role == Utilisateur.Role.PROFESSEUR:
        return examens.filter(
            cours__affectations_professeurs__professeur=request.user,
            periode_id=F("cours__affectations_professeurs__periode_id"),
        ).distinct()
    if request.user.role == Utilisateur.Role.ETUDIANT:
        return examens.filter(
            cours__selections_inscription__inscription__etudiant=request.user,
            cours__selections_inscription__inscription__statut=(
                InscriptionPedagogique.Statut.VALIDEE
            ),
            cours__selections_inscription__inscription__conditions_passage_verifiees=True,
            periode_id=F("cours__selections_inscription__inscription__periode_id"),
        ).distinct()
    raise PermissionDenied


@login_required
def calendrier_examens(request):
    examens = _examens_visibles(request).order_by("date_debut", "cours__code")
    return render(request, "notes/calendrier_examens.django", {"examens": examens})


def _examens_modifiables(request):
    if request.user.is_superuser:
        return ProgrammationExamen.objects.all()
    if request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id:
        raise PermissionDenied
    return ProgrammationExamen.objects.filter(
        cours__programme__entite_id=request.user.entite_id
    )


@login_required
def gestion_examens(request, examen_id=None):
    examens = _examens_modifiables(request)
    examen = None
    if examen_id is not None:
        examen = get_object_or_404(
            examens.select_related("cours", "periode"), pk=examen_id
        )

    if request.method == "POST":
        formulaire = FormulaireProgrammationExamen(
            request.POST,
            utilisateur=request.user,
            instance=examen,
        )
        if formulaire.is_valid():
            objet = formulaire.save(commit=False)
            est_nouveau = objet.pk is None
            if est_nouveau:
                objet.planifie_par = request.user
            try:
                objet.full_clean()
            except ValidationError as erreur:
                formulaire.add_error(None, erreur)
            else:
                objet.save()
                JournalAction.objects.create(
                    utilisateur=request.user,
                    action="examen.planifie" if est_nouveau else "examen.modifie",
                    type_objet="ProgrammationExamen",
                    identifiant_objet=str(objet.pk),
                    details={
                        "cours": objet.cours.code,
                        "periode": objet.periode.code,
                        "libelle": objet.libelle,
                        "statut": objet.statut,
                    },
                    adresse_ip=request.META.get("REMOTE_ADDR"),
                )
                messages.success(request, "L'examen a ete enregistre.")
                return redirect("notes:gestion_examens")
    else:
        formulaire = FormulaireProgrammationExamen(
            utilisateur=request.user,
            instance=examen,
        )

    examens = examens.select_related("cours__programme", "periode").order_by(
        "date_debut", "cours__code"
    )
    return render(
        request,
        "notes/gestion_examens.django",
        {"formulaire": formulaire, "examens": examens, "examen_modifie": examen},
    )
