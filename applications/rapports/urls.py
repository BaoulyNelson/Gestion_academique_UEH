from django.urls import path

from .views import (
    acte_imprimable,
    actes_etudiant,
    exporter_rapports_csv,
    gestion_dossiers,
    gestion_actes,
    gestion_soutenances,
    liste_etudiants,
    liste_paiements_acquittes,
    proces_verbal_soutenance_imprimable,
    proces_verbaux_soutenances,
    telecharger_acte_pdf,
    telecharger_proces_verbal_pdf,
    tableau_rapports,
)

app_name = "rapports"

urlpatterns = [
    path("", tableau_rapports, name="tableau"),
    path("exporter.csv", exporter_rapports_csv, name="exporter_csv"),
    path("registrariat/listes-etudiants/", liste_etudiants, name="liste_etudiants"),
    path(
        "registrariat/paiements-acquittes/",
        liste_paiements_acquittes,
        name="liste_paiements_acquittes",
    ),
    path("mes-actes/", actes_etudiant, name="actes_etudiant"),
    path("registrariat/actes/", gestion_actes, name="gestion_actes"),
    path("registrariat/dossiers/", gestion_dossiers, name="gestion_dossiers"),
    path(
        "registrariat/dossiers/<int:dossier_id>/modifier/",
        gestion_dossiers,
        name="modifier_dossier",
    ),
    path(
        "registrariat/soutenances/",
        gestion_soutenances,
        name="gestion_soutenances",
    ),
    path(
        "registrariat/soutenances/<int:soutenance_id>/modifier/",
        gestion_soutenances,
        name="modifier_soutenance",
    ),
    path("mes-actes/<int:acte_id>/imprimer/", acte_imprimable, name="acte_imprimable"),
    path(
        "mes-actes/<int:acte_id>/telecharger.pdf",
        telecharger_acte_pdf,
        name="telecharger_acte_pdf",
    ),
    path("proces-verbaux/", proces_verbaux_soutenances, name="proces_verbaux"),
    path(
        "proces-verbaux/<int:soutenance_id>/imprimer/",
        proces_verbal_soutenance_imprimable,
        name="proces_verbal_imprimable",
    ),
    path(
        "proces-verbaux/<int:soutenance_id>/telecharger.pdf",
        telecharger_proces_verbal_pdf,
        name="telecharger_proces_verbal_pdf",
    ),
]
