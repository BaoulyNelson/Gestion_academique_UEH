from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from applications.candidats.models import Candidat
from applications.comptes.models import Utilisateur
from applications.candidatures.models import Inscription
from applications.documents.forms import DocumentCandidatForm
from applications.documents.models import DocumentCandidat
from applications.entites.models import AdministrateurEntite, Entite


class DocumentsCandidatTests(TestCase):
    def setUp(self):
        self.repertoire_temporaire = TemporaryDirectory()
        self.addCleanup(self.repertoire_temporaire.cleanup)
        reglages_media = override_settings(MEDIA_ROOT=self.repertoire_temporaire.name)
        reglages_media.enable()
        self.addCleanup(reglages_media.disable)
        self.utilisateur = Utilisateur.objects.create_user(
            "proprietaire@example.com", "MotDePasse-Securise-2026"
        )
        self.candidat = Candidat.objects.create(utilisateur=self.utilisateur)
        self.entite = Entite.objects.create(code="FDS", nom="Faculté des Sciences")

    def formulaire(self, nom, contenu):
        fichier = SimpleUploadedFile(nom, contenu, content_type="application/pdf")
        return DocumentCandidatForm(
            data={"type_document": DocumentCandidat.TypeDocument.NAISSANCE},
            files={"fichier": fichier},
        )

    def test_formats_autorises_et_taille_maximale(self):
        self.assertTrue(self.formulaire("acte.pdf", b"%PDF-1.4").is_valid())
        formulaire_invalide = self.formulaire("acte.exe", b"contenu")
        self.assertFalse(formulaire_invalide.is_valid())
        formulaire_trop_volumineux = self.formulaire(
            "acte.pdf", b"x" * (2 * 1024 * 1024 + 1)
        )
        self.assertFalse(formulaire_trop_volumineux.is_valid())

    def test_telechargement_prive_au_candidat_et_a_son_entite(self):
        inscription = Inscription.objects.create(
            candidat=self.candidat,
            entite=self.entite,
            annee_academique="2026-2027",
        )
        document = DocumentCandidat.objects.create(
            candidat=self.candidat,
            type_document=DocumentCandidat.TypeDocument.NAISSANCE,
            fichier=SimpleUploadedFile("acte.pdf", b"%PDF-1.4"),
        )
        administrateur = Utilisateur.objects.create_user(
            "gestionnaire@example.com", "MotDePasse-Securise-2026", is_staff=True
        )
        AdministrateurEntite.objects.create(
            utilisateur=administrateur, entite=self.entite
        )
        self.client.force_login(administrateur)
        reponse = self.client.get(f"/documents/{document.pk}/telecharger/")
        self.assertEqual(reponse.status_code, 200)
        reponse.close()
        autre_utilisateur = Utilisateur.objects.create_user(
            "autre@example.com", "MotDePasse-Securise-2026"
        )
        self.client.force_login(autre_utilisateur)
        self.assertEqual(
            self.client.get(f"/documents/{document.pk}/telecharger/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("documents:apercu", args=[document.pk])
            ).status_code,
            404,
        )

    def test_apercu_document_est_inline_et_same_origin(self):
        document = DocumentCandidat.objects.create(
            candidat=self.candidat,
            type_document=DocumentCandidat.TypeDocument.NAISSANCE,
            fichier=SimpleUploadedFile("acte.pdf", b"%PDF-1.4"),
        )
        self.client.force_login(self.utilisateur)

        reponse = self.client.get(reverse("documents:apercu", args=[document.pk]))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse["Content-Type"], "application/pdf")
        self.assertTrue(reponse["Content-Disposition"].startswith("inline;"))
        self.assertEqual(reponse["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(reponse["Cache-Control"], "private, no-store")
        reponse.close()
