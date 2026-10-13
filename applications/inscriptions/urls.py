from django.urls import path

from .views import (
    decider_paiement,
    decider_inscription,
    choix_cours_etudiant,
    inscription_etudiant,
    imprimer_fiche_inscription,
    inscriptions_a_traiter,
    liste_cours_professeur,
    liste_cours_etudiant,
    liste_etudiants_professeur,
    liste_professeurs_etudiant,
    paiements_a_verifier,
    paiements_etudiant,
    telecharger_recu_paiement,
    verifier_dossier_etudiant,
)

app_name = "inscriptions"

urlpatterns = [
    path("mes-cours/", liste_cours_professeur, name="cours_professeur"),
    path("mes-cours-etudiant/", liste_cours_etudiant, name="cours_etudiant"),
    path(
        "mes-etudiants/",
        liste_etudiants_professeur,
        name="etudiants_professeur",
    ),
    path(
        "mes-professeurs/",
        liste_professeurs_etudiant,
        name="professeurs_etudiant",
    ),
    path("pedagogiques/", inscription_etudiant, name="inscription_etudiant"),
    path(
        "pedagogiques/<int:inscription_id>/fiche/",
        imprimer_fiche_inscription,
        name="fiche_inscription",
    ),
    path(
        "pedagogiques/a-traiter/",
        inscriptions_a_traiter,
        name="inscriptions_a_traiter",
    ),
    path(
        "pedagogiques/<int:inscription_id>/cours/",
        choix_cours_etudiant,
        name="choix_cours_etudiant",
    ),
    path(
        "pedagogiques/<int:inscription_id>/decision/",
        decider_inscription,
        name="decider_inscription",
    ),
    path("paiements/", paiements_etudiant, name="paiement_etudiant"),
    path(
        "paiements/<int:paiement_id>/recu.pdf",
        telecharger_recu_paiement,
        name="recu_paiement",
    ),
    path("paiements/a-verifier/", paiements_a_verifier, name="paiements_a_verifier"),
    path(
        "registrariat/verifier-dossier/",
        verifier_dossier_etudiant,
        name="verifier_dossier",
    ),
    path(
        "paiements/<int:paiement_id>/decision/",
        decider_paiement,
        name="decider_paiement",
    ),
]
