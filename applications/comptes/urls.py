from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .views import (
    ConnexionView,
    DeconnexionView,
    configuration_site,
    landing_page,
    PhotoProfilAdministrateurView,
    ProfilAdministrateurEntiteView,
    profil,
    tableau_de_bord,
)

app_name = "comptes"

urlpatterns = [
    path("", landing_page, name="landing"),
    path("accueil/", landing_page, name="landing_alt"),
    path("connexion/", ConnexionView.as_view(), name="connexion"),
    path("mon-profil/", profil, name="profil"),
    path("configuration-site/", configuration_site, name="configuration_site"),
    path("deconnexion/", DeconnexionView.as_view(), name="deconnexion"),
    path(
        "mot-de-passe/oublie/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("comptes:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "mot-de-passe/envoye/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "mot-de-passe/nouveau/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("comptes:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "mot-de-passe/termine/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("tableau-de-bord/", tableau_de_bord, name="tableau_de_bord"),
    path(
        "admission/mon-profil/",
        ProfilAdministrateurEntiteView.as_view(),
        name="profil_administrateur",
    ),
    path(
        "admission/photo-profil/",
        PhotoProfilAdministrateurView.as_view(),
        name="photo_profil",
    ),
]
