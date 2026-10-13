from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, Value
from django.db.models.functions import Coalesce

from applications.comptes.models import ProfilEtudiant, Utilisateur
from applications.inscriptions.models import (
    InscriptionPedagogique,
    TarifScolarite,
)
from applications.inscriptions.services.paiements import frais_scolarite_acquittes
from applications.notes.models import Evaluation
from applications.notes.services.resultats import (
    calculer_moyenne_ponderee,
    evaluation_eliminatoire,
)
from applications.rapports.models import (
    ActeAcademique,
    DossierEtudes,
    SoutenanceMemoire,
)
from applications.referentiels.models import RegleAcademique


def _repartition_par_sexe(queryset, *dimensions):
    queryset = queryset.annotate(
        sexe=Coalesce(
            "etudiant__profil_etudiant__sexe",
            Value(ProfilEtudiant.Sexe.NON_RENSEIGNE),
        )
    )
    return list(
        queryset.values(*dimensions, "sexe")
        .annotate(nombre=Count("pk"))
        .order_by(*dimensions, "sexe")
    )


def _seuils_reussite_cours(periode):
    if not periode.date_debut:
        return None, None, None, None
    regle = (
        RegleAcademique.objects.filter(
            entite_id=periode.entite_id,
            est_active=True,
            date_effet__lte=periode.date_debut,
        )
        .order_by("-date_effet")
        .first()
    )
    if not regle:
        return None, None, None, None
    if not isinstance(regle.parametres, dict):
        return None, None, regle.version, None
    try:
        seuil_reussite = Decimal(str(regle.parametres["seuil_reussite_cours"]))
        seuil_reprise = Decimal(
            str(regle.parametres.get("seuil_reprise_cours", seuil_reussite))
        )
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return None, None, regle.version, None
    if (
        not seuil_reussite.is_finite()
        or not Decimal("0") <= seuil_reussite <= Decimal("100")
        or not seuil_reprise.is_finite()
        or not Decimal("0") <= seuil_reprise <= seuil_reussite
    ):
        return None, None, regle.version, None
    try:
        credits_requis = Decimal(str(regle.parametres.get("credits_requis", 0)))
    except (InvalidOperation, TypeError, ValueError):
        credits_requis = None
    if credits_requis is not None and (
        not credits_requis.is_finite() or credits_requis <= 0
    ):
        credits_requis = None
    return seuil_reussite, seuil_reprise, regle.version, credits_requis


def evaluer_inscriptions_passage(inscriptions):
    inscriptions = list(inscriptions)
    if not inscriptions:
        return inscriptions

    identifiants_etudiants = {inscription.etudiant_id for inscription in inscriptions}
    identifiants_programmes = {inscription.programme_id for inscription in inscriptions}
    identifiants_periodes = {inscription.periode_id for inscription in inscriptions}
    evaluations_par_cours = defaultdict(list)
    evaluations = Evaluation.objects.filter(
        etudiant_id__in=identifiants_etudiants,
        cours__programme_id__in=identifiants_programmes,
        periode_id__in=identifiants_periodes,
        est_publiee=True,
    ).select_related("cours")
    for evaluation in evaluations:
        evaluations_par_cours[
            (
                evaluation.etudiant_id,
                evaluation.cours.programme_id,
                evaluation.periode_id,
                evaluation.cours_id,
            )
        ].append(evaluation)

    regles_par_periode = {
        periode_id: _seuils_reussite_cours(
            next(
                inscription.periode
                for inscription in inscriptions
                if inscription.periode_id == periode_id
            )
        )
        for periode_id in identifiants_periodes
    }
    libelles = {
        "reussite": "Reussite",
        "reprise": "A reprendre",
        "echec": "Echec",
        "en_attente": "En attente de notes ou de regle",
        "frais_non_acquittes": "Frais de scolarite non acquittes",
    }
    tarifs = {
        (tarif.programme_id, tarif.periode_id): tarif
        for tarif in TarifScolarite.objects.filter(
            programme_id__in=identifiants_programmes,
            periode_id__in=identifiants_periodes,
            est_actif=True,
        ).select_related("programme")
    }

    for inscription in inscriptions:
        seuil_reussite, seuil_reprise, version, credits_regle = regles_par_periode[
            inscription.periode_id
        ]
        inscription.version_regle_passage = version
        selections = list(inscription.cours_selectionnes.select_related("cours"))
        evaluations_des_cours = [
            evaluations_par_cours[
                (
                    inscription.etudiant_id,
                    inscription.programme_id,
                    inscription.periode_id,
                    selection.cours_id,
                )
            ]
            for selection in selections
        ]
        moyennes = [
            calculer_moyenne_ponderee(evaluations_cours)
            for evaluations_cours in evaluations_des_cours
        ]
        tarif = tarifs.get((inscription.programme_id, inscription.periode_id))
        frais_acquittes = (
            frais_scolarite_acquittes(inscription.etudiant, tarif) if tarif else None
        )
        if (
            not selections
            or seuil_reussite is None
            or seuil_reprise is None
            or any(moyenne is None for moyenne in moyennes)
        ):
            statut = "en_attente"
        elif any(
            evaluation_eliminatoire(evaluations_cours, inscription.periode)
            for evaluations_cours in evaluations_des_cours
        ):
            statut = "echec"
        else:
            credits_requis = inscription.programme.credits_requis or credits_regle
            credits_acquis = sum(
                (
                    selection.cours.credits
                    for selection, moyenne in zip(selections, moyennes)
                    if moyenne >= seuil_reussite
                ),
                Decimal("0"),
            )
            moyenne_globale = sum(
                (
                    moyenne * selection.cours.credits
                    for selection, moyenne in zip(selections, moyennes)
                ),
                Decimal("0"),
            )
            credits_totaux = sum(
                (selection.cours.credits for selection in selections), Decimal("0")
            )
            if credits_totaux > 0:
                moyenne_globale /= credits_totaux
            else:
                moyenne_globale = sum(moyennes, Decimal("0")) / len(moyennes)

            credits_suffisants = (
                credits_requis is not None and credits_acquis >= credits_requis
            )
            if credits_suffisants or moyenne_globale >= seuil_reussite:
                statut = "reussite"
            elif any(moyenne < seuil_reprise for moyenne in moyennes):
                statut = "echec"
            else:
                statut = "reprise"
        inscription.statut_passage_academique = statut
        inscription.statut_passage_academique_display = libelles[statut]
        inscription.frais_scolarite_acquittes = frais_acquittes
        statut_liste = "frais_non_acquittes" if frais_acquittes is False else statut
        inscription.statut_passage = statut_liste
        inscription.statut_passage_display = libelles[statut_liste]
    return inscriptions


def calculer_statistiques_cours(entite, periode=None, programme=None):
    evaluations = Evaluation.objects.filter(
        cours__programme__entite=entite,
        est_publiee=True,
    ).select_related("cours", "periode", "etudiant")
    if periode:
        evaluations = evaluations.filter(periode=periode)
    if programme:
        evaluations = evaluations.filter(cours__programme=programme)

    groupes_etudiants = defaultdict(list)
    for evaluation in evaluations.order_by(
        "periode__annee_academique", "periode__date_debut", "cours__code", "libelle"
    ):
        groupes_etudiants[
            (evaluation.cours_id, evaluation.periode_id, evaluation.etudiant_id)
        ].append(evaluation)

    groupes_cours = {}
    for (cours_id, periode_id, _), notes in groupes_etudiants.items():
        premiere = notes[0]
        cle = (cours_id, periode_id)
        groupe = groupes_cours.setdefault(
            cle,
            {
                "cours": premiere.cours,
                "periode": premiere.periode,
                "etudiants": [],
            },
        )
        groupe["etudiants"].append(
            (premiere.etudiant, calculer_moyenne_ponderee(notes), notes)
        )

    libelles_sexes = dict(ProfilEtudiant.Sexe.choices)
    resultats = []
    for groupe in groupes_cours.values():
        seuil_reussite, seuil_reprise, version_regle, _ = _seuils_reussite_cours(
            groupe["periode"]
        )
        ventilation = defaultdict(lambda: {"reussites": 0, "reprises": 0, "echecs": 0})
        reussites = 0
        reprises = 0
        echecs = 0
        if seuil_reussite is not None:
            for etudiant, moyenne, notes in groupe["etudiants"]:
                profil = getattr(etudiant, "profil_etudiant", None)
                sexe = getattr(profil, "sexe", ProfilEtudiant.Sexe.NON_RENSEIGNE)
                if evaluation_eliminatoire(notes, groupe["periode"]):
                    echecs += 1
                    ventilation[sexe]["echecs"] += 1
                elif moyenne >= seuil_reussite:
                    reussites += 1
                    ventilation[sexe]["reussites"] += 1
                elif moyenne >= seuil_reprise:
                    reprises += 1
                    ventilation[sexe]["reprises"] += 1
                else:
                    echecs += 1
                    ventilation[sexe]["echecs"] += 1

        resultats.append(
            {
                "cours": groupe["cours"],
                "programme": groupe["cours"].programme,
                "periode": groupe["periode"],
                "version_regle": version_regle,
                "seuil_reussite": seuil_reussite,
                "seuil_reprise": seuil_reprise,
                "nombre_etudiants": len(groupe["etudiants"]),
                "reussites": reussites if seuil_reussite is not None else None,
                "reprises": reprises if seuil_reussite is not None else None,
                "echecs": echecs if seuil_reussite is not None else None,
                "repartition_sexe": [
                    {
                        "sexe": sexe,
                        "sexe_display": libelles_sexes.get(sexe, sexe),
                        **valeurs,
                    }
                    for sexe, valeurs in sorted(ventilation.items())
                ],
            }
        )
    return resultats


def calculer_indicateurs(entite, periode=None, programme=None):
    etudiants = Utilisateur.objects.filter(
        role=Utilisateur.Role.ETUDIANT,
        entite=entite,
    )
    inscriptions = InscriptionPedagogique.objects.filter(programme__entite=entite)
    dossiers = DossierEtudes.objects.filter(programme__entite=entite)
    actes = ActeAcademique.objects.filter(
        programme__entite=entite,
        est_annule=False,
    )
    soutenances = SoutenanceMemoire.objects.filter(programme__entite=entite)

    if programme:
        etudiants = etudiants.filter(inscriptions_pedagogiques__programme=programme)
        inscriptions = inscriptions.filter(programme=programme)
        dossiers = dossiers.filter(programme=programme)
        actes = actes.filter(programme=programme)
        soutenances = soutenances.filter(programme=programme)
    if periode:
        etudiants = etudiants.filter(inscriptions_pedagogiques__periode=periode)
        inscriptions = inscriptions.filter(periode=periode)
        actes = actes.filter(periode=periode)
        soutenances = soutenances.filter(periode=periode)

    etudiants = etudiants.distinct()
    profils = ProfilEtudiant.objects.filter(utilisateur__in=etudiants)
    repartition_sexe = list(
        profils.values("sexe").annotate(nombre=Count("pk")).order_by("sexe")
    )
    nombre_profils = profils.count()
    nombre_sexe_non_renseigne = (
        etudiants.filter(
            Q(profil_etudiant__isnull=True)
            | Q(profil_etudiant__sexe=ProfilEtudiant.Sexe.NON_RENSEIGNE)
        )
        .distinct()
        .count()
    )

    repartition_dossiers_sexe = _repartition_par_sexe(dossiers, "statut")
    repartition_actes_sexe = _repartition_par_sexe(actes, "type_acte")
    repartition_soutenances_sexe = _repartition_par_sexe(
        soutenances.filter(statut=SoutenanceMemoire.Statut.SOUTENUE)
    )
    libelles_statuts_dossiers = dict(DossierEtudes.Statut.choices)
    libelles_types_actes = dict(ActeAcademique.TypeActe.choices)
    libelles_sexes = dict(ProfilEtudiant.Sexe.choices)
    for ligne in repartition_dossiers_sexe:
        ligne["statut_display"] = libelles_statuts_dossiers[ligne["statut"]]
    for ligne in repartition_actes_sexe:
        ligne["type_acte_display"] = libelles_types_actes[ligne["type_acte"]]
    for ligne in (
        repartition_sexe
        + repartition_dossiers_sexe
        + repartition_actes_sexe
        + repartition_soutenances_sexe
    ):
        ligne["sexe_display"] = libelles_sexes.get(ligne["sexe"], ligne["sexe"])

    return {
        "nombre_etudiants": etudiants.count(),
        "nombre_profils_renseignes": nombre_profils,
        "nombre_sexe_non_renseigne": nombre_sexe_non_renseigne,
        "repartition_sexe": repartition_sexe,
        "nombre_inscriptions": inscriptions.count(),
        "nombre_inscriptions_en_attente": inscriptions.filter(
            statut=InscriptionPedagogique.Statut.EN_ATTENTE
        ).count(),
        "nombre_inscriptions_validees": inscriptions.filter(
            statut=InscriptionPedagogique.Statut.VALIDEE
        ).count(),
        "nombre_dossiers": dossiers.count(),
        "dossiers_en_cours": dossiers.filter(
            statut=DossierEtudes.Statut.EN_COURS
        ).count(),
        "dossiers_fermes": dossiers.filter(statut=DossierEtudes.Statut.FERME).count(),
        "abandons": dossiers.filter(statut=DossierEtudes.Statut.ABANDON).count(),
        "repartition_dossiers_sexe": repartition_dossiers_sexe,
        "nombre_actes": actes.count(),
        "nombre_diplomes": actes.filter(
            type_acte=ActeAcademique.TypeActe.DIPLOME
        ).count(),
        "nombre_attestations_certificats": actes.filter(
            type_acte__in=(
                ActeAcademique.TypeActe.ATTESTATION_INSCRIPTION,
                ActeAcademique.TypeActe.ATTESTATION_ETUDES,
                ActeAcademique.TypeActe.CERTIFICAT,
            )
        ).count(),
        "repartition_actes_sexe": repartition_actes_sexe,
        "nombre_soutenances": soutenances.filter(
            statut=SoutenanceMemoire.Statut.SOUTENUE
        ).count(),
        "repartition_soutenances_sexe": repartition_soutenances_sexe,
    }
