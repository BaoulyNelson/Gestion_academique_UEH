from django.urls import path

from applications.candidats.views import (
    communes_departement,
    mon_profil,
    apercu_ecole,
    apercu_parcours,
    photo_identite,
    telecharger_ecole,
    telecharger_parcours,
)

app_name = "candidats"
urlpatterns = [
    path("mon-profil/", mon_profil, name="mon_profil"),
    path("photo-identite/", photo_identite, name="photo_identite"),
    path("communes/", communes_departement, name="communes"),
    path("ecoles/<int:pk>/certificat/", telecharger_ecole, name="certificat_ecole"),
    path("ecoles/<int:pk>/apercu/", apercu_ecole, name="apercu_ecole"),
    path(
        "etudes/<int:pk>/<str:champ>/",
        telecharger_parcours,
        name="document_parcours",
    ),
    path(
        "etudes/<int:pk>/<str:champ>/apercu/",
        apercu_parcours,
        name="apercu_parcours",
    ),
]
