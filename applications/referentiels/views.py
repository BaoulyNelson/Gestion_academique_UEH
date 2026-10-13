from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from applications.audit.models import JournalAction
from applications.comptes.models import Utilisateur

from .forms import FormulaireRegleAcademique
from .models import Entite, RegleAcademique


def _regles_modifiables(request):
    if request.user.is_superuser:
        return RegleAcademique.objects.all()
    if request.user.role != Utilisateur.Role.PERSONNEL or not request.user.entite_id:
        raise PermissionDenied
    return RegleAcademique.objects.filter(entite_id=request.user.entite_id)


@login_required
def gestion_regles_academiques(request, regle_id=None):
    regles = _regles_modifiables(request)
    entites = (
        Entite.objects.all()
        if request.user.is_superuser
        else Entite.objects.filter(pk=request.user.entite_id)
    )
    regle = None
    if regle_id is not None:
        regle = get_object_or_404(regles.select_related("entite"), pk=regle_id)

    if request.method == "POST":
        formulaire = FormulaireRegleAcademique(
            request.POST,
            utilisateur=request.user,
            instance=regle,
        )
        if formulaire.is_valid():
            objet = formulaire.save(commit=False)
            est_nouvelle = objet.pk is None
            try:
                objet.full_clean()
            except ValidationError as erreur:
                formulaire.add_error(None, erreur)
            else:
                objet.save()
                JournalAction.objects.create(
                    utilisateur=request.user,
                    action=(
                        "regle_academique.creee"
                        if est_nouvelle
                        else "regle_academique.modifiee"
                    ),
                    type_objet="RegleAcademique",
                    identifiant_objet=str(objet.pk),
                    details={
                        "entite": objet.entite.code,
                        "version": objet.version,
                        "date_effet": objet.date_effet.isoformat(),
                        "parametres": objet.parametres,
                    },
                    adresse_ip=request.META.get("REMOTE_ADDR"),
                )
                messages.success(request, "La regle academique a ete enregistree.")
                return redirect("referentiels:regles_academiques")
    else:
        formulaire = FormulaireRegleAcademique(
            utilisateur=request.user,
            instance=regle,
        )

    return render(
        request,
        "referentiels/regles_academiques.django",
        {
            "formulaire": formulaire,
            "regles": regles.select_related("entite"),
            "entites": entites,
            "regle_modifiee": regle,
        },
    )
