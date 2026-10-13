import csv

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from applications.administration.mixins import EntiteAdminRequiredMixin
from applications.administration.forms import (
    AffectationSalleForm,
    DocumentsCandidatFormSet,
    EcolesCandidatFormSet,
    EpreuvesResultatFormSet,
    FormulaireDossierCandidat,
    FormulaireHoraire,
    FormulaireOption,
    FormulaireResultat,
    FormulaireSalle,
    ParcoursCandidatFormSet,
)
from applications.administration.models import JournalAction
from applications.candidats.models import Candidat
from applications.candidatures.models import Inscription
from applications.entites.models import (
    HoraireEntite,
    Option,
    Salle,
    entites_autorisees,
)
from applications.resultats.models import Resultat


class ValidationInscriptionView(EntiteAdminRequiredMixin, View):
    def post(self, request, pk):
        with transaction.atomic():
            inscription = get_object_or_404(
                self.get_queryset().select_for_update(), pk=pk
            )
            inscription.statut = Inscription.Statut.VALIDE
            inscription.save(update_fields=["statut"])
            JournalAction.objects.create(
                utilisateur=request.user,
                inscription=inscription,
                entite=inscription.entite,
                action=JournalAction.Action.VALIDATION,
            )
        messages.success(request, "Le dossier a été validé.")
        return render(
            request, "administration/action_terminee.html", {"inscription": inscription}
        )


class RejetInscriptionView(EntiteAdminRequiredMixin, View):
    def post(self, request, pk):
        motif = request.POST.get("motif", "")[:1000]
        with transaction.atomic():
            inscription = get_object_or_404(
                self.get_queryset().select_for_update(), pk=pk
            )
            inscription.statut = Inscription.Statut.REJETE
            inscription.save(update_fields=["statut"])
            JournalAction.objects.create(
                utilisateur=request.user,
                inscription=inscription,
                entite=inscription.entite,
                action=JournalAction.Action.REJET,
                details={"motif": motif},
            )
        messages.success(request, "Le dossier a été rejeté.")
        return render(
            request, "administration/action_terminee.html", {"inscription": inscription}
        )


class SuppressionInscriptionView(EntiteAdminRequiredMixin, View):
    def post(self, request, pk):
        with transaction.atomic():
            inscription = get_object_or_404(
                self.get_queryset().select_for_update(), pk=pk
            )
            JournalAction.objects.create(
                utilisateur=request.user,
                inscription=inscription,
                entite=inscription.entite,
                action=JournalAction.Action.SUPPRESSION,
                details={"numero_dossier": inscription.numero_dossier},
            )
            inscription.delete()
        messages.success(request, "Le dossier a été supprimé.")
        return redirect("administration:liste_inscriptions")


class AffectationSalleInscriptionView(EntiteAdminRequiredMixin, View):
    def get(self, request, pk):
        inscription = self.get_inscription()
        formulaire = AffectationSalleForm(entite=inscription.entite)
        formulaire.fields["salle"].initial = inscription.salle_id
        return render(
            request,
            "administration/affecter_salle.html",
            {"inscription": inscription, "formulaire": formulaire},
        )

    def post(self, request, pk):
        inscription = self.get_inscription()
        formulaire = AffectationSalleForm(request.POST, entite=inscription.entite)
        if formulaire.is_valid():
            with transaction.atomic():
                inscription = self.get_queryset().select_for_update().get(pk=pk)
                inscription.salle = formulaire.cleaned_data["salle"]
                inscription.save(update_fields=["salle"])
                JournalAction.objects.create(
                    utilisateur=request.user,
                    inscription=inscription,
                    entite=inscription.entite,
                    action=JournalAction.Action.AFFECTATION_SALLE,
                )
            messages.success(request, "La salle du dossier a été mise à jour.")
            return render(
                request,
                "administration/action_terminee.html",
                {"inscription": inscription},
            )
        return render(
            request,
            "administration/affecter_salle.html",
            {"inscription": inscription, "formulaire": formulaire},
            status=400,
        )


class ListeInscriptionsEntiteView(EntiteAdminRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "administration/liste_inscriptions.html",
            {"inscriptions": self.get_queryset()},
        )


class GestionRessourceEntiteView(EntiteAdminRequiredMixin, View):
    modele = None
    formulaire = None
    nom_ressource = ""
    nom_url = ""
    action_creation = ""
    action_modification = ""
    action_suppression = ""

    def get_queryset(self, request):
        queryset = self.modele.objects.select_related("entite")
        autorisees = entites_autorisees(request.user)
        return (
            queryset if autorisees is None else queryset.filter(entite__in=autorisees)
        )

    def afficher(self, request, formulaire=None, objet_modifie=None, status=200):
        if formulaire is None:
            formulaire = self.formulaire(utilisateur=request.user)
        return render(
            request,
            "administration/gestion_ressources.html",
            {
                "formulaire": formulaire,
                "ressources": self.get_queryset(request),
                "nom_ressource": self.nom_ressource,
                "nom_url": self.nom_url,
                "url_ressource": reverse(self.nom_url),
                "objet_modifie": objet_modifie,
            },
            status=status,
        )

    def details(self, objet):
        details = {"ressource": str(objet)}
        if hasattr(objet, "capacite"):
            details["capacite"] = objet.capacite
        if hasattr(objet, "active"):
            details["actif"] = objet.active
        if hasattr(objet, "actif"):
            details["actif"] = objet.actif
        return details

    def get(self, request, pk=None):
        pk = pk or request.GET.get("modifier")
        objet_modifie = (
            get_object_or_404(self.get_queryset(request), pk=pk) if pk else None
        )
        formulaire = self.formulaire(utilisateur=request.user, instance=objet_modifie)
        return self.afficher(request, formulaire, objet_modifie)

    def post(self, request, pk=None):
        pk = pk or request.POST.get("pk")
        if request.POST.get("action") == "supprimer":
            objet = get_object_or_404(self.get_queryset(request), pk=pk)
            try:
                with transaction.atomic():
                    JournalAction.objects.create(
                        utilisateur=request.user,
                        entite=objet.entite,
                        action=self.action_suppression,
                        details=self.details(objet),
                    )
                    objet.delete()
            except ProtectedError:
                messages.error(
                    request,
                    "Cette ressource est utilisée et ne peut pas être supprimée.",
                )
                return redirect(self.nom_url)
            messages.success(request, f"{self.nom_ressource} supprimé(e).")
            return redirect(self.nom_url)

        objet_modifie = (
            get_object_or_404(self.get_queryset(request), pk=pk) if pk else None
        )
        formulaire = self.formulaire(
            request.POST,
            utilisateur=request.user,
            instance=objet_modifie,
        )
        if formulaire.is_valid():
            nouvelle_ressource = objet_modifie is None
            with transaction.atomic():
                objet = formulaire.save()
                JournalAction.objects.create(
                    utilisateur=request.user,
                    entite=objet.entite,
                    action=(
                        self.action_creation
                        if nouvelle_ressource
                        else self.action_modification
                    ),
                    details=self.details(objet),
                )
            messages.success(request, f"{self.nom_ressource} enregistré(e).")
            return redirect(self.nom_url)
        return self.afficher(request, formulaire, objet_modifie, status=400)


class GestionSallesView(GestionRessourceEntiteView):
    modele = Salle
    formulaire = FormulaireSalle
    nom_ressource = "Salle"
    nom_url = "administration:liste_salles"
    action_creation = JournalAction.Action.CREATION_SALLE
    action_modification = JournalAction.Action.MODIFICATION_SALLE
    action_suppression = JournalAction.Action.SUPPRESSION_SALLE


class GestionOptionsView(GestionRessourceEntiteView):
    modele = Option
    formulaire = FormulaireOption
    nom_ressource = "Option"
    nom_url = "administration:liste_options"
    action_creation = JournalAction.Action.CREATION_OPTION
    action_modification = JournalAction.Action.MODIFICATION_OPTION
    action_suppression = JournalAction.Action.SUPPRESSION_OPTION


class GestionHorairesView(GestionRessourceEntiteView):
    modele = HoraireEntite
    formulaire = FormulaireHoraire
    nom_ressource = "Horaire"
    nom_url = "administration:liste_horaires"
    action_creation = JournalAction.Action.CREATION_HORAIRE
    action_modification = JournalAction.Action.MODIFICATION_HORAIRE
    action_suppression = JournalAction.Action.SUPPRESSION_HORAIRE


class JournalEntiteView(EntiteAdminRequiredMixin, View):
    def get(self, request):
        autorisees = entites_autorisees(request.user)
        actions = JournalAction.objects.select_related(
            "utilisateur", "entite", "inscription"
        )
        if autorisees is not None:
            actions = actions.filter(entite__in=autorisees)

        action_choisie = request.GET.get("action", "")
        choix_valides = dict(JournalAction.Action.choices)
        if action_choisie in choix_valides:
            actions = actions.filter(action=action_choisie)
        else:
            action_choisie = ""

        page_obj = Paginator(actions, 50).get_page(request.GET.get("page"))
        return render(
            request,
            "administration/journal_actions.html",
            {
                "page_obj": page_obj,
                "actions": page_obj.object_list,
                "choix_actions": JournalAction.Action.choices,
                "action_choisie": action_choisie,
            },
        )


class GestionDossierCandidatView(EntiteAdminRequiredMixin, View):
    def afficher(self, request, inscription, formulaire, formsets, status=200):
        return render(
            request,
            "administration/modifier_candidat.html",
            {
                "inscription": inscription,
                "formulaire": formulaire,
                "formsets": formsets,
            },
            status=status,
        )

    def get(self, request, pk):
        inscription = self.get_inscription()
        candidat = inscription.candidat
        formulaire = FormulaireDossierCandidat(instance=candidat)
        formsets = (
            {
                "titre": "Écoles fréquentées",
                "formset": EcolesCandidatFormSet(instance=candidat, prefix="ecoles"),
            },
            {
                "titre": "Parcours d’études",
                "formset": ParcoursCandidatFormSet(
                    instance=candidat, prefix="parcours"
                ),
            },
            {
                "titre": "Documents du dossier",
                "formset": DocumentsCandidatFormSet(
                    instance=candidat, prefix="documents"
                ),
            },
        )
        return self.afficher(request, inscription, formulaire, formsets)

    def post(self, request, pk):
        inscription = self.get_inscription()
        candidat = inscription.candidat
        formulaire = FormulaireDossierCandidat(request.POST, instance=candidat)
        formsets = (
            {
                "titre": "Écoles fréquentées",
                "formset": EcolesCandidatFormSet(
                    request.POST, request.FILES, instance=candidat, prefix="ecoles"
                ),
            },
            {
                "titre": "Parcours d’études",
                "formset": ParcoursCandidatFormSet(
                    request.POST,
                    request.FILES,
                    instance=candidat,
                    prefix="parcours",
                ),
            },
            {
                "titre": "Documents du dossier",
                "formset": DocumentsCandidatFormSet(
                    request.POST,
                    request.FILES,
                    instance=candidat,
                    prefix="documents",
                ),
            },
        )
        formsets_valides = [groupe["formset"].is_valid() for groupe in formsets]
        if formulaire.is_valid() and all(formsets_valides):
            collections_modifiees = {
                groupe["formset"].prefix: sum(
                    form.has_changed() for form in groupe["formset"].forms
                )
                for groupe in formsets
                if any(form.has_changed() for form in groupe["formset"].forms)
            }
            champs_modifies = list(formulaire.changed_data)
            with transaction.atomic():
                candidat = formulaire.save()
                for groupe in formsets:
                    formset = groupe["formset"]
                    formset.instance = candidat
                    formset.save()
                JournalAction.objects.create(
                    utilisateur=request.user,
                    inscription=inscription,
                    entite=inscription.entite,
                    action=JournalAction.Action.MODIFICATION_DOSSIER,
                    details={
                        "champs_modifies": champs_modifies,
                        "collections_modifiees": collections_modifiees,
                    },
                )
            messages.success(request, "Le dossier du candidat a été mis à jour.")
            return redirect("resultats:mes_resultats")
        return self.afficher(request, inscription, formulaire, formsets, status=400)


class GestionResultatView(EntiteAdminRequiredMixin, View):
    def afficher(self, request, inscription, resultat, formulaire, formset, status=200):
        return render(
            request,
            "administration/modifier_resultat.html",
            {
                "inscription": inscription,
                "resultat": resultat,
                "formulaire": formulaire,
                "formset": formset,
            },
            status=status,
        )

    def construire_formulaires(self, request, inscription, resultat=None):
        resultat = resultat or Resultat(inscription=inscription)
        formulaire = FormulaireResultat(
            request.POST or None,
            instance=resultat,
        )
        formset = EpreuvesResultatFormSet(
            request.POST or None,
            instance=resultat,
            prefix="epreuves",
        )
        return resultat, formulaire, formset

    def get(self, request, pk):
        inscription = self.get_inscription()
        resultat = Resultat.objects.filter(inscription=inscription).first()
        resultat, formulaire, formset = self.construire_formulaires(
            request, inscription, resultat
        )
        return self.afficher(request, inscription, resultat, formulaire, formset)

    def post(self, request, pk):
        inscription = self.get_inscription()
        resultat = Resultat.objects.filter(inscription=inscription).first()
        resultat, formulaire, formset = self.construire_formulaires(
            request, inscription, resultat
        )
        formulaire_valide = formulaire.is_valid()
        formset_valide = formset.is_valid()
        if formulaire_valide and formset_valide:
            nouvelle_resultat = resultat.pk is None
            with transaction.atomic():
                resultat = formulaire.save(commit=False)
                resultat.inscription = inscription
                if resultat.publie and resultat.date_publication is None:
                    resultat.date_publication = timezone.now()
                elif not resultat.publie:
                    resultat.date_publication = None
                resultat.save()
                formset.instance = resultat
                formset.save()
                resultat.note = resultat.moyenne_calculee
                resultat.admis = resultat.admis_calcule
                resultat.save(update_fields=["note", "admis"])
                JournalAction.objects.create(
                    utilisateur=request.user,
                    inscription=inscription,
                    entite=inscription.entite,
                    action=(
                        JournalAction.Action.CREATION_RESULTAT
                        if nouvelle_resultat
                        else JournalAction.Action.MODIF_RESULTAT
                    ),
                    details={
                        "nombre_epreuves": resultat.epreuves.count(),
                        "publie": resultat.publie,
                        "moyenne": str(resultat.note or ""),
                    },
                )
            messages.success(request, "Le résultat a été enregistré.")
            return redirect("resultats:mes_resultats")
        return self.afficher(
            request, inscription, resultat, formulaire, formset, status=400
        )


class ExportInscriptionsView(EntiteAdminRequiredMixin, View):
    def get(self, request):
        reponse = HttpResponse(content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = 'attachment; filename="inscriptions.csv"'
        reponse.write("\ufeff")
        ecrivain = csv.writer(reponse, delimiter=";")
        ecrivain.writerow(
            ["Numéro de dossier", "Candidat", "Entité", "Année académique", "Statut"]
        )
        for inscription in self.get_queryset():
            ecrivain.writerow(
                [
                    inscription.numero_dossier,
                    inscription.candidat.utilisateur.get_full_name()
                    or inscription.candidat.utilisateur.email,
                    inscription.entite,
                    inscription.annee_academique,
                    inscription.get_statut_display(),
                ]
            )
        return reponse
