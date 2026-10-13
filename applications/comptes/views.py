from mimetypes import guess_type

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.db.models import F
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from applications.comptes.forms import (
    FormulaireConfigurationSite,
    FormulaireProfilAdministrateur,
)
from applications.comptes.models import ProfilEtudiant, SiteConfiguration, Utilisateur
from applications.entites.models import entites_autorisees
from applications.inscriptions.models import InscriptionPedagogique, SelectionCours
from applications.notes.models import Evaluation
from applications.rapports.models import DossierEtudes
from applications.referentiels.models import (
    AffectationCours,
    Cours,
    Entite,
    PeriodeAcademique,
    Programme,
)


class ConnexionView(LoginView):
    template_name = "registration/connexion.html"
    redirect_authenticated_user = True


class DeconnexionView(LogoutView):
    http_method_names = ["post"]


class ProfilAdministrateurEntiteRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            entites = entites_autorisees(request.user)
            if entites is None or not entites.exists():
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ProfilAdministrateurEntiteView(ProfilAdministrateurEntiteRequiredMixin, View):
    def get(self, request):
        formulaire = FormulaireProfilAdministrateur(instance=request.user)
        return render(
            request,
            "account/profil_administrateur.html",
            {"formulaire": formulaire},
        )

    def post(self, request):
        formulaire = FormulaireProfilAdministrateur(
            request.POST,
            request.FILES,
            instance=request.user,
        )
        if formulaire.is_valid():
            formulaire.save()
            messages.success(request, "Votre profil a été mis à jour.")
            return redirect("comptes:profil_administrateur")
        return render(
            request,
            "account/profil_administrateur.html",
            {"formulaire": formulaire},
            status=400,
        )


class PhotoProfilAdministrateurView(ProfilAdministrateurEntiteRequiredMixin, View):
    def get(self, request):
        photo = request.user.photo_profil
        if not photo:
            raise Http404
        nom_fichier = photo.name.rsplit("/", 1)[-1]
        reponse = FileResponse(
            photo.open("rb"),
            as_attachment=False,
            filename=nom_fichier,
            content_type=guess_type(nom_fichier)[0] or "application/octet-stream",
        )
        reponse["Cache-Control"] = "private, no-store"
        reponse["X-Content-Type-Options"] = "nosniff"
        return reponse


def landing_page(request):
    config = SiteConfiguration.get_solo()
    entites_actives = Entite.objects.filter(est_active=True)
    statistiques = {
        "entites": entites_actives.count(),
        "programmes": Programme.objects.filter(
            entite__in=entites_actives, est_actif=True
        ).count(),
        "etudiants": (
            InscriptionPedagogique.objects.filter(
                programme__entite__in=entites_actives,
                statut=InscriptionPedagogique.Statut.VALIDEE,
            )
            .values("etudiant_id")
            .distinct()
            .count()
        ),
        "professeurs": Utilisateur.objects.filter(
            role=Utilisateur.Role.PROFESSEUR,
            entite__in=entites_actives,
            is_active=True,
        ).count(),
        "cours": Cours.objects.filter(
            programme__entite__in=entites_actives,
            programme__est_actif=True,
            est_actif=True,
        ).count(),
    }
    programmes = (
        Programme.objects.filter(entite__in=entites_actives, est_actif=True)
        .select_related("entite")
        .order_by("entite__nom", "nom")[:8]
    )
    periodes = (
        PeriodeAcademique.objects.filter(
            entite__in=entites_actives,
            date_debut__isnull=False,
            date_fin__gte=timezone.localdate(),
        )
        .select_related("entite")
        .order_by("date_debut", "nom")[:5]
    )
    return render(
        request,
        "public/landing_page.html",
        {
            "site_config": config,
            "statistiques": statistiques,
            "programmes": programmes,
            "periodes": periodes,
            "annee_courante": timezone.localdate().year,
        },
    )


@login_required
def profil(request):
    if request.method == "POST" and request.FILES.get("photo_profil"):
        request.user.photo_profil = request.FILES["photo_profil"]
        request.user.save(update_fields=["photo_profil"])
        messages.success(request, "Votre photo de profil a ete mise a jour.")
        return redirect("comptes:profil")

    contexte = {"user": request.user}
    if request.user.role == Utilisateur.Role.ETUDIANT:
        contexte["profil_etudiant"] = ProfilEtudiant.objects.filter(
            utilisateur=request.user
        ).first()
        contexte["dossiers_etudes"] = DossierEtudes.objects.filter(
            etudiant=request.user
        ).select_related("programme", "programme__entite")

    return render(request, "portail/profil.django", contexte)


@login_required
def configuration_site(request):
    if not (
        request.user.is_superuser
        or request.user.role == Utilisateur.Role.ADMINISTRATEUR
    ):
        raise PermissionDenied

    configuration = SiteConfiguration.get_solo()
    formulaire = FormulaireConfigurationSite(
        request.POST or None,
        request.FILES or None,
        instance=configuration,
    )
    if request.method == "POST" and formulaire.is_valid():
        formulaire.save()
        messages.success(request, "La configuration du site a ete enregistree.")
        return redirect("comptes:configuration_site")

    return render(
        request,
        "portail/configuration_site.django",
        {"formulaire": formulaire, "configuration": configuration},
    )


@login_required
def tableau_de_bord(request):
    entite = request.user.entite
    inscriptions = InscriptionPedagogique.objects.all()
    utilisateurs = Utilisateur.objects.all()
    evaluations = Evaluation.objects.all()
    nombre_cours_professeur = 0

    if request.user.is_superuser:
        entites = Entite.objects.count()
        programmes = Programme.objects.all()
    elif request.user.role == Utilisateur.Role.PERSONNEL and entite:
        inscriptions = inscriptions.filter(programme__entite=entite)
        utilisateurs = utilisateurs.filter(entite=entite)
        evaluations = evaluations.filter(cours__programme__entite=entite)
        entites = Entite.objects.filter(pk=entite.pk).count()
        programmes = Programme.objects.filter(entite=entite)
    elif request.user.role == Utilisateur.Role.ETUDIANT:
        inscriptions = inscriptions.filter(etudiant=request.user)
        utilisateurs = utilisateurs.filter(pk=request.user.pk)
        evaluations = evaluations.filter(etudiant=request.user, est_publiee=True)
        entites = int(entite is not None)
        programmes = Programme.objects.filter(
            inscriptions__etudiant=request.user
        ).distinct()
    elif request.user.role == Utilisateur.Role.PROFESSEUR:
        selections = SelectionCours.objects.filter(
            cours__affectations_professeurs__professeur=request.user,
            cours__affectations_professeurs__periode_id=F("inscription__periode_id"),
            inscription__statut=InscriptionPedagogique.Statut.VALIDEE,
        )
        inscriptions = InscriptionPedagogique.objects.filter(
            pk__in=selections.values("inscription_id")
        )
        utilisateurs = Utilisateur.objects.filter(
            pk__in=selections.values("inscription__etudiant_id")
        )
        evaluations = Evaluation.objects.filter(
            cours__affectations_professeurs__professeur=request.user,
            cours__affectations_professeurs__periode_id=F("periode_id"),
        ).distinct()
        entites = (
            Entite.objects.filter(
                programmes__cours__affectations_professeurs__professeur=request.user
            )
            .distinct()
            .count()
        )
        programmes = Programme.objects.filter(
            cours__affectations_professeurs__professeur=request.user
        ).distinct()
        nombre_cours_professeur = (
            AffectationCours.objects.filter(professeur=request.user)
            .values("cours_id")
            .distinct()
            .count()
        )
    else:
        inscriptions = inscriptions.none()
        utilisateurs = utilisateurs.none()
        evaluations = evaluations.none()
        entites = 0
        programmes = Programme.objects.none()

    context = {
        "nombre_entites": entites,
        "nombre_programmes": programmes.count(),
        "nombre_cours_professeur": nombre_cours_professeur,
        "nombre_etudiants": utilisateurs.filter(role=Utilisateur.Role.ETUDIANT).count(),
        "nombre_inscriptions": inscriptions.count(),
        "nombre_notes_a_valider": evaluations.filter(est_publiee=False).count(),
        "nombre_notes_publiees": evaluations.filter(est_publiee=True).count(),
        "activite_recente": inscriptions.select_related(
            "etudiant", "programme", "periode"
        ).order_by("-date_creation")[:6],
    }
    return render(request, "portail/tableau_de_bord.django", context)
