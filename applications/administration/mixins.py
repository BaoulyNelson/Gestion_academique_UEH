from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from applications.candidatures.models import Inscription
from applications.entites.models import entites_autorisees


class EntiteAdminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        autorisees = entites_autorisees(request.user)
        if not request.user.is_superuser and (
            autorisees is None or not autorisees.exists()
        ):
            raise PermissionDenied("Vous n’êtes administrateur d’aucune entité.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Inscription.objects.pour_utilisateur(self.request.user).select_related(
            "candidat__utilisateur", "entite", "option", "salle"
        )

    def get_inscription(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
