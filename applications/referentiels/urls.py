from django.urls import path

from .views import gestion_regles_academiques

app_name = "referentiels"

urlpatterns = [
    path("regles-academiques/", gestion_regles_academiques, name="regles_academiques"),
    path(
        "regles-academiques/<int:regle_id>/modifier/",
        gestion_regles_academiques,
        name="modifier_regle_academique",
    ),
]
