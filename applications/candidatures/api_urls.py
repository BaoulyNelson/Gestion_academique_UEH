from django.urls import path

from applications.candidatures.api_views import ListeInscriptionsAPI

urlpatterns = [
    path("inscriptions/", ListeInscriptionsAPI.as_view(), name="api_inscriptions")
]
