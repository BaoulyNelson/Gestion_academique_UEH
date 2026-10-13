from django.urls import path

from applications.candidatures.views import creer_inscription
from applications.tableau_bord import views

app_name = "tableau_bord"
urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("guide/", views.accueil, {"rubrique": "guide"}, name="guide_public"),
    path("entites/", views.accueil, {"rubrique": "entites"}, name="entites_publiques"),
    path(
        "statistiques/",
        views.accueil,
        {"rubrique": "statistiques"},
        name="statistiques_publiques",
    ),
    path("a-propos/", views.accueil, {"rubrique": "a_propos"}, name="a_propos_public"),
    path("guide-documents/", views.guide_documents, name="guide_documents"),
    path("mes-inscriptions/", views.mes_inscriptions, name="mes_inscriptions"),
    path("mes-inscriptions/nouvelle/", creer_inscription, name="nouvelle_inscription"),
]
