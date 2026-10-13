from django.http import Http404
from django.shortcuts import redirect


class ProtectionAdministrationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/") and request.user.is_authenticated:
            if not request.user.is_superuser and request.user.est_administrateur_entite:
                return redirect("administration:liste_inscriptions")
            if not request.user.is_superuser:
                raise Http404
        return self.get_response(request)
