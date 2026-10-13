from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Optional

from applications.notes.models import Evaluation
from applications.referentiels.models import RegleAcademique


def calculer_moyenne_ponderee(evaluations: Iterable[Evaluation]) -> Optional[Decimal]:
    total_pondere = Decimal("0")
    total_coefficients = Decimal("0")
    nombre_evaluations = 0

    for evaluation in evaluations:
        note = Decimal(evaluation.note)
        coefficient = Decimal(evaluation.coefficient)
        if not Decimal("0") <= note <= Decimal("100"):
            raise ValueError("Une note doit etre comprise entre 0 et 100.")
        if coefficient <= 0:
            raise ValueError("Le coefficient doit etre strictement positif.")
        total_pondere += note * coefficient
        total_coefficients += coefficient
        nombre_evaluations += 1

    if not nombre_evaluations:
        return None
    return (total_pondere / total_coefficients).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def constantes_academiques(periode):
    if not periode.date_debut:
        return {}
    regle = (
        RegleAcademique.objects.filter(
            entite_id=periode.entite_id,
            est_active=True,
            date_effet__lte=periode.date_debut,
        )
        .order_by("-date_effet")
        .first()
    )
    return regle.parametres if regle and isinstance(regle.parametres, dict) else {}


def note_eliminatoire_pour_periode(periode):
    valeur = constantes_academiques(periode).get("note_eliminatoire")
    if valeur is None:
        return None
    try:
        seuil = Decimal(str(valeur))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not seuil.is_finite() or not Decimal("0") <= seuil <= Decimal("100"):
        return None
    return seuil


def evaluation_eliminatoire(evaluations, periode):
    seuil = note_eliminatoire_pour_periode(periode)
    return seuil is not None and any(
        Decimal(evaluation.note) < seuil for evaluation in evaluations
    )


def mention_pour_moyenne(periode, moyenne):
    mentions = constantes_academiques(periode).get("mentions", {})
    if moyenne is None or not isinstance(mentions, dict):
        return None
    seuils = []
    for nom, valeur in mentions.items():
        try:
            seuil = Decimal(str(valeur))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if seuil.is_finite() and Decimal("0") <= seuil <= Decimal("100"):
            seuils.append((seuil, nom))
    admissibles = [(seuil, nom) for seuil, nom in seuils if Decimal(moyenne) >= seuil]
    return max(admissibles)[1] if admissibles else None


def calculer_moyennes_academiques(evaluations: Iterable[Evaluation]):
    notes_par_cours = defaultdict(list)
    cours_par_programme_etudiant = defaultdict(list)
    cours_par_periode_etudiant = defaultdict(list)
    identifiants = {}

    groupes = defaultdict(list)
    for evaluation in evaluations:
        cle = (evaluation.etudiant_id, evaluation.cours_id, evaluation.periode_id)
        groupes[cle].append(evaluation)
        identifiants[cle] = evaluation

    for cle, evaluations_cours in groupes.items():
        moyenne = calculer_moyenne_ponderee(evaluations_cours)
        premiere = identifiants[cle]
        if moyenne is None:
            continue
        credits = Decimal(premiere.cours.credits)
        cle_cours = (premiere.cours_id, premiere.periode_id)
        notes_par_cours[cle_cours].append(moyenne)
        cours_par_programme_etudiant[
            (premiere.etudiant_id, premiere.cours.programme_id, premiere.periode_id)
        ].append((moyenne, credits))
        cours_par_periode_etudiant[(premiere.etudiant_id, premiere.periode_id)].append(
            (moyenne, credits)
        )

    def moyenne_credits(valeurs):
        total_credits = sum((credits for _, credits in valeurs), Decimal("0"))
        if total_credits:
            total = sum(
                (moyenne * credits for moyenne, credits in valeurs), Decimal("0")
            )
            return total / total_credits
        return sum((moyenne for moyenne, _ in valeurs), Decimal("0")) / len(valeurs)

    def arrondir(valeur):
        return valeur.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    moyennes_cours = []
    for (cours_id, periode_id), valeurs in notes_par_cours.items():
        premiere = next(
            evaluation
            for cle, evaluation in identifiants.items()
            if cle[1:] == (cours_id, periode_id)
        )
        moyennes_cours.append(
            {
                "cours": premiere.cours,
                "periode": premiere.periode,
                "moyenne": arrondir(sum(valeurs, Decimal("0")) / len(valeurs)),
                "nombre_etudiants": len(valeurs),
            }
        )

    valeurs_programme = defaultdict(list)
    for (
        etudiant_id,
        programme_id,
        periode_id,
    ), valeurs in cours_par_programme_etudiant.items():
        premiere = next(
            evaluation
            for cle, evaluation in identifiants.items()
            if cle[0] == etudiant_id
            and cle[2] == periode_id
            and evaluation.cours.programme_id == programme_id
        )
        valeurs_programme[(programme_id, periode_id)].append(
            (moyenne_credits(valeurs), premiere.cours.programme)
        )

    moyennes_programmes = []
    for (programme_id, periode_id), valeurs in valeurs_programme.items():
        premiere = next(
            evaluation
            for cle, evaluation in identifiants.items()
            if cle[2] == periode_id and evaluation.cours.programme_id == programme_id
        )
        moyennes_programmes.append(
            {
                "programme": premiere.cours.programme,
                "periode": premiere.periode,
                "moyenne": arrondir(
                    sum((moyenne for moyenne, _ in valeurs), Decimal("0"))
                    / len(valeurs)
                ),
                "nombre_etudiants": len(valeurs),
            }
        )

    valeurs_periode = defaultdict(list)
    for (etudiant_id, periode_id), valeurs in cours_par_periode_etudiant.items():
        valeurs_periode[periode_id].append(moyenne_credits(valeurs))

    moyennes_periodes = []
    for periode_id, valeurs in valeurs_periode.items():
        premiere = next(
            evaluation
            for evaluation in identifiants.values()
            if evaluation.periode_id == periode_id
        )
        moyennes_periodes.append(
            {
                "periode": premiere.periode,
                "moyenne": arrondir(sum(valeurs, Decimal("0")) / len(valeurs)),
                "nombre_etudiants": len(valeurs),
            }
        )

    return {
        "cours": sorted(
            moyennes_cours,
            key=lambda ligne: (
                (ligne["programme"].nom, ligne["periode"], ligne["cours"].code)
                if "programme" in ligne
                else (
                    ligne["cours"].programme.nom,
                    ligne["periode"],
                    ligne["cours"].code,
                )
            ),
        ),
        "programmes": sorted(
            moyennes_programmes,
            key=lambda ligne: (ligne["programme"].nom, ligne["periode"]),
        ),
        "periodes": sorted(moyennes_periodes, key=lambda ligne: ligne["periode"]),
    }
