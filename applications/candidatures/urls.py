from django.urls import path

from applications.candidatures import views

app_name = "candidatures"
urlpatterns = [
    path("nouvelle/", views.creer_inscription, name="creer"),
    path(
        "nouvelle/brouillon/",
        views.sauvegarder_brouillon_inscription,
        name="sauvegarder_brouillon",
    ),
    path("choix-entite/", views.choix_entite, name="choix_entite"),
    path("<int:pk>/", views.detail_inscription, name="detail"),
    path("<int:pk>/recu/", views.recu_inscription, name="recu"),
    path(
        "<int:pk>/recu-paiement/",
        views.telecharger_recu_paiement,
        name="telecharger_recu_paiement",
    ),
    path("<int:pk>/pdf/", views.pdf_inscription, name="pdf"),
]
