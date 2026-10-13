from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Mapping, Optional, Tuple, Union

ValeurNote = Union[Decimal, int, float, str]


class TypeDecision(Enum):
    ADMIS = "admis"
    REPRISE = "reprise"
    ECHEC = "echec"
    REDOUBLEMENT = "redoublement"
    EXCLUSION = "exclusion"
    REVUE_MANUELLE = "revue_manuelle"


@dataclass(frozen=True)
class DecisionPassage:
    type_decision: TypeDecision
    annee_etude: int
    moyenne_annuelle: Decimal
    cours_a_reprendre: Tuple[str, ...] = ()
    motif: str = ""


def _normaliser_note(valeur: ValeurNote, libelle: str) -> Decimal:
    try:
        note = Decimal(str(valeur))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"La note '{libelle}' doit etre un nombre valide.")

    if not note.is_finite() or note < 0 or note > 100:
        raise ValueError(f"La note '{libelle}' doit etre comprise entre 0 et 100.")
    return note


def evaluer_passage_famv_2016(
    annee_etude: int,
    moyenne_annuelle: ValeurNote,
    notes_cours: Mapping[str, ValeurNote],
    moyenne_premiere_session: Optional[ValeurNote] = None,
) -> DecisionPassage:
    """Classe la moyenne selon les seuils retenus pour le cahier des charges."""
    if annee_etude not in range(1, 6):
        raise ValueError("L'annee d'etude doit etre comprise entre 1 et 5.")
    if not notes_cours:
        raise ValueError("Au moins une note finale par cours est requise.")

    moyenne = _normaliser_note(moyenne_annuelle, "moyenne annuelle")
    notes = {code: _normaliser_note(note, code) for code, note in notes_cours.items()}

    if moyenne < 60:
        return DecisionPassage(
            TypeDecision.ECHEC,
            annee_etude,
            moyenne,
            motif="Moyenne annuelle inferieure a 60/100.",
        )

    if moyenne < 65:
        cours_a_reprendre = tuple(code for code, note in notes.items() if note < 65)
        if not cours_a_reprendre:
            return DecisionPassage(
                TypeDecision.REVUE_MANUELLE,
                annee_etude,
                moyenne,
                motif="Moyenne annuelle et notes de cours incoherentes; verifier le dossier.",
            )
        return DecisionPassage(
            TypeDecision.REPRISE,
            annee_etude,
            moyenne,
            cours_a_reprendre,
            "Moyenne annuelle de 60 a moins de 65/100; reprendre les cours sous 65 (art. 101).",
        )

    return DecisionPassage(
        TypeDecision.ADMIS,
        annee_etude,
        moyenne,
        motif="Moyenne annuelle d'au moins 65/100.",
    )
