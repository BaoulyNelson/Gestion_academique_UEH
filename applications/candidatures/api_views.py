from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from applications.candidats.models import Candidat
from applications.candidatures.models import Inscription
from applications.candidatures.serializers import SerializeurInscription
from applications.entites.models import entites_autorisees


class ListeInscriptionsAPI(ListAPIView):
    serializer_class = SerializeurInscription
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        utilisateur = self.request.user
        if utilisateur.is_superuser:
            return Inscription.objects.select_related("entite", "option", "salle")
        autorisees = entites_autorisees(utilisateur)
        if autorisees is not None and autorisees.exists():
            return Inscription.objects.pour_utilisateur(utilisateur).select_related(
                "entite", "option", "salle"
            )
        return Inscription.objects.filter(
            candidat__utilisateur=utilisateur
        ).select_related("entite", "option", "salle")
