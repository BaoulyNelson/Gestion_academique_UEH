from django.contrib import messages
from django.contrib.auth.decorators import login_required
from mimetypes import guess_type
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django_ratelimit.decorators import ratelimit
from django.views.decorators.clickjacking import xframe_options_sameorigin

from applications.candidats.models import Candidat
from applications.candidatures.models import Inscription
from applications.candidatures.progression import (
    champs_profil_manquants,
    documents_manquants,
)
from applications.documents.forms import DocumentCandidatForm
from applications.documents.models import DocumentCandidat
from applications.entites.models import entites_autorisees


@login_required
@ratelimit(key="user", rate="10/h", method="POST", block=True)
def mes_documents(request):
    if request.user.is_staff:
        return redirect("tableau_bord:mes_inscriptions")
    candidat = get_object_or_404(Candidat, utilisateur=request.user)
    if (
        request.session.get("reprendre_candidature")
        and not champs_profil_manquants(candidat)
        and not documents_manquants(candidat)
    ):
        request.session.pop("reprendre_candidature", None)
        return redirect("candidatures:creer")
    if request.method == "POST":
        formulaire = DocumentCandidatForm(request.POST, request.FILES)
        if formulaire.is_valid():
            document = formulaire.save(commit=False)
            document.candidat = candidat
            document.save()
            messages.success(request, "Votre document a été téléversé.")
            if request.session.get("reprendre_candidature"):
                if not documents_manquants(candidat):
                    request.session.pop("reprendre_candidature", None)
                    return redirect("candidatures:creer")
                messages.info(
                    request,
                    "Il reste des pièces justificatives à téléverser avant de continuer.",
                )
            return redirect("documents:mes_documents")
    else:
        formulaire = DocumentCandidatForm()
    return render(
        request,
        "documents/mes_documents.html",
        {
            "formulaire": formulaire,
            "documents": candidat.documents.all(),
            "documents_manquants": [
                (
                    "Document NIF ou NINU"
                    if code == "IDENTIFIANT"
                    else dict(DocumentCandidat.TypeDocument.choices)[code]
                )
                for code in documents_manquants(candidat)
            ],
        },
    )


def document_visible_par(request, pk):
    document = get_object_or_404(
        DocumentCandidat.objects.select_related("candidat__utilisateur"), pk=pk
    )
    if document.candidat.utilisateur_id != request.user.pk:
        autorisees = entites_autorisees(request.user)
        if request.user.is_superuser:
            pass
        elif (
            autorisees is None
            or not Inscription.objects.pour_utilisateur(request.user)
            .filter(candidat=document.candidat)
            .exists()
        ):
            from django.http import Http404

            raise Http404
    return document


@login_required
@xframe_options_sameorigin
def apercu_document(request, pk):
    document = document_visible_par(request, pk)
    nom_fichier = document.fichier.name.rsplit("/", 1)[-1]
    reponse = FileResponse(
        document.fichier.open("rb"),
        as_attachment=False,
        filename=nom_fichier,
        content_type=guess_type(nom_fichier)[0] or "application/octet-stream",
    )
    reponse["Cache-Control"] = "private, no-store"
    reponse["X-Content-Type-Options"] = "nosniff"
    return reponse


@login_required
def telecharger_document(request, pk):
    document = document_visible_par(request, pk)
    return FileResponse(
        document.fichier.open("rb"),
        as_attachment=True,
        filename=document.fichier.name.rsplit("/", 1)[-1],
    )
