from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),

    # --- Admission (ancien 2e projet) ---
    path("admission/api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "admission/api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("admission/api/", include("applications.candidatures.api_urls")),
    path("admission/candidatures/", include("applications.candidatures.urls")),
    path("admission/candidats/", include("applications.candidats.urls")),
    path("admission/documents/", include("applications.documents.urls")),
    path("admission/resultats/", include("applications.resultats.urls")),
    path("admission/gestion/", include("applications.administration.urls")),
    path("admission/", include("applications.tableau_bord.urls")),

    # --- Authentification allauth (une seule fois) ---
    path("comptes/", include("allauth.urls")),

    # --- GP7 ---
    path("inscriptions/", include("applications.inscriptions.urls")),
    path("notes/", include("applications.notes.urls")),
    path("rapports/", include("applications.rapports.urls")),
    path("referentiels/", include("applications.referentiels.urls")),
    path("contact/", include("applications.contact.urls")),
    path("", include("applications.comptes.urls")),  # en dernier (préfixe vide)
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)