from django.urls import path

from applications.resultats.views import imprimer_resultat, mes_resultats

app_name = "resultats"
urlpatterns = [
    path("mes-resultats/", mes_resultats, name="mes_resultats"),
    path("<int:pk>/imprimer/", imprimer_resultat, name="imprimer_resultat"),
]
