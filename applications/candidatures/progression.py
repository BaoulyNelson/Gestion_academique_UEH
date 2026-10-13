from django.utils import timezone

from applications.documents.models import DocumentCandidat

CHAMPS_PERSONNELS_REQUIS = (
    "nationalite",
    "telephone",
    "date_naissance",
    "lieu_naissance",
    "sexe",
)

CHAMPS_ADRESSE_REQUIS = ("adresse", "departement_geographique", "ville")
CHAMPS_PROFIL_REQUIS = (
    *CHAMPS_PERSONNELS_REQUIS,
    *CHAMPS_ADRESSE_REQUIS,
    "etablissement_scolaire",
    "annee_obtention",
)

DOCUMENTS_REQUIS = (
    DocumentCandidat.TypeDocument.NAISSANCE,
    DocumentCandidat.TypeDocument.PHOTO,
    DocumentCandidat.TypeDocument.DIPLOME,
)


def champs_profil_manquants(candidat):
    manquants = champs_personnels_manquants(candidat)
    manquants.extend(champs_adresse_manquants(candidat))
    if not candidat.ecoles.exists():
        manquants.append("ecole_et_certificat")
    return manquants


def champs_personnels_manquants(candidat):
    manquants = [
        champ for champ in CHAMPS_PERSONNELS_REQUIS if not getattr(candidat, champ)
    ]
    manquants.extend(
        champ for champ in ("prenom", "nom") if not getattr(candidat.utilisateur, champ)
    )
    if not candidat.nif and not candidat.ninu:
        manquants.append("nif_ou_ninu")
    if candidat.date_naissance:
        aujourd_hui = timezone.localdate()
        age = (
            aujourd_hui.year
            - candidat.date_naissance.year
            - (
                (aujourd_hui.month, aujourd_hui.day)
                < (candidat.date_naissance.month, candidat.date_naissance.day)
            )
        )
        if age < 18 and not candidat.nom_parent_responsable:
            manquants.append("nom_parent_responsable")
    return manquants


def champs_adresse_manquants(candidat):
    return [champ for champ in CHAMPS_ADRESSE_REQUIS if not getattr(candidat, champ)]


def documents_manquants(candidat):
    televerses = set(
        candidat.documents.values_list("type_document", flat=True).distinct()
    )
    manquants = [
        document
        for document in (
            DocumentCandidat.TypeDocument.NAISSANCE,
            DocumentCandidat.TypeDocument.PHOTO,
        )
        if document not in televerses
    ]
    types_identifiants = set()
    if candidat.nif:
        types_identifiants.add(DocumentCandidat.TypeDocument.NIF)
    if candidat.ninu:
        types_identifiants.add(DocumentCandidat.TypeDocument.NINU)
    if types_identifiants and not types_identifiants.intersection(televerses):
        manquants.append("IDENTIFIANT")
    return manquants
