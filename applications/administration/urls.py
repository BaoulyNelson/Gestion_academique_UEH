from django.urls import path

from applications.administration.views import (
    AffectationSalleInscriptionView,
    ExportInscriptionsView,
    GestionDossierCandidatView,
    GestionHorairesView,
    GestionOptionsView,
    GestionResultatView,
    GestionSallesView,
    JournalEntiteView,
    ListeInscriptionsEntiteView,
    RejetInscriptionView,
    SuppressionInscriptionView,
    ValidationInscriptionView,
)

app_name = "administration"
urlpatterns = [
    path("journal/", JournalEntiteView.as_view(), name="journal_actions"),
    path("salles/", GestionSallesView.as_view(), name="liste_salles"),
    path("options/", GestionOptionsView.as_view(), name="liste_options"),
    path("horaires/", GestionHorairesView.as_view(), name="liste_horaires"),
    path(
        "inscriptions/<int:pk>/salle/",
        AffectationSalleInscriptionView.as_view(),
        name="affecter_salle",
    ),
    path(
        "inscriptions/<int:pk>/candidat/",
        GestionDossierCandidatView.as_view(),
        name="modifier_candidat",
    ),
    path(
        "inscriptions/<int:pk>/resultat/",
        GestionResultatView.as_view(),
        name="gerer_resultat",
    ),
    path(
        "inscriptions/",
        ListeInscriptionsEntiteView.as_view(),
        name="liste_inscriptions",
    ),
    path(
        "inscriptions/exporter/",
        ExportInscriptionsView.as_view(),
        name="export_inscriptions",
    ),
    path(
        "inscriptions/<int:pk>/valider/",
        ValidationInscriptionView.as_view(),
        name="valider_inscription",
    ),
    path(
        "inscriptions/<int:pk>/rejeter/",
        RejetInscriptionView.as_view(),
        name="rejeter_inscription",
    ),
    path(
        "inscriptions/<int:pk>/supprimer/",
        SuppressionInscriptionView.as_view(),
        name="supprimer_inscription",
    ),
]
