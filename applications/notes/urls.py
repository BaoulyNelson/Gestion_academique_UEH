from django.urls import path

from .views import (
    calendrier_examens,
    gestion_examens,
    liste_evaluations,
    notes_a_publier,
    importer_evaluations_excel,
    publier_notes_cours,
    releves_etudiants,
    resultats_etudiant,
    saisir_evaluation,
    retirer_publication_note,
)

app_name = "notes"

urlpatterns = [
    path("mes-resultats/", resultats_etudiant, name="resultats_etudiant"),
    path("releves-etudiants/", releves_etudiants, name="releves_etudiants"),
    path("calendrier-examens/", calendrier_examens, name="calendrier_examens"),
    path("examens/gestion/", gestion_examens, name="gestion_examens"),
    path(
        "examens/gestion/<int:examen_id>/",
        gestion_examens,
        name="modifier_examen",
    ),
    path("a-publier/", notes_a_publier, name="notes_a_publier"),
    path("evaluations/", liste_evaluations, name="liste_evaluations"),
    path(
        "cours/<int:cours_id>/periodes/<int:periode_id>/saisir/",
        saisir_evaluation,
        name="saisir_evaluation",
    ),
    path(
        "cours/<int:cours_id>/periodes/<int:periode_id>/importer/",
        importer_evaluations_excel,
        name="importer_evaluations_excel",
    ),
    path(
        "cours/<int:cours_id>/periodes/<int:periode_id>/publier/",
        publier_notes_cours,
        name="publier_notes_cours",
    ),
    path(
        "evaluations/<int:evaluation_id>/retirer-publication/",
        retirer_publication_note,
        name="retirer_publication_note",
    ),
]
