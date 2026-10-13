from concurrent.futures import ThreadPoolExecutor
import re
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.core import mail
from django.db import close_old_connections
from django.test import (
    TestCase,
    TransactionTestCase,
    override_settings,
    skipUnlessDBFeature,
)
from django.urls import reverse
from django.utils import timezone
from allauth.account.models import EmailAddress

from applications.administration.models import JournalAction
from applications.candidats.models import Candidat, EcoleCandidat
from applications.candidats.forms import ProfilCandidatForm
from applications.candidats.etapes_forms import InformationsPersonnellesForm
from applications.comptes.models import Utilisateur
from applications.candidatures.models import Inscription
from applications.candidatures.models import BrouillonInscription
from applications.documents.models import DocumentCandidat
from applications.entites.models import (
    AdministrateurEntite,
    Entite,
    HoraireEntite,
    Option,
    Salle,
)
from applications.referentiels.models import Entite as EntiteGP7


class AccesParEntiteTests(TestCase):
    def setUp(self):
        self.entite_a = Entite.objects.create(code="FDS", nom="Faculté des Sciences")
        self.entite_b = Entite.objects.create(
            code="FASCH", nom="Faculté des Sciences Humaines"
        )
        self.utilisateur_candidat = Utilisateur.objects.create_user(
            "candidat@example.com", "MotDePasse-Securise-2026"
        )
        self.candidat = Candidat.objects.create(utilisateur=self.utilisateur_candidat)
        self.inscription_a = self.creer_inscription(self.entite_a)
        self.inscription_b = self.creer_inscription(self.entite_b)
        self.admin_entite = Utilisateur.objects.create_user(
            "admin-a@example.com", "MotDePasse-Securise-2026", is_staff=True
        )
        AdministrateurEntite.objects.create(
            utilisateur=self.admin_entite, entite=self.entite_a
        )
        self.client.force_login(self.admin_entite)

    def creer_inscription(self, entite):
        return Inscription.objects.create(
            candidat=self.candidat,
            entite=entite,
            annee_academique="2026-2027",
        )

    def preparer_etapes_precedentes(self):
        self.utilisateur_candidat.prenom = "Marie"
        self.utilisateur_candidat.nom = "Jean"
        self.utilisateur_candidat.save(update_fields=["prenom", "nom"])
        self.candidat.telephone = "509 1234-5678"
        self.candidat.date_naissance = "2000-01-15"
        self.candidat.lieu_naissance = "Port-au-Prince"
        self.candidat.adresse = "Rue de la Paix"
        self.candidat.ville = "Port-au-Prince"
        self.candidat.sexe = Candidat.Sexe.FEMININ
        self.candidat.departement_geographique = Candidat.Departement.OUEST
        self.candidat.nif = "000-000-000-0"
        self.candidat.etablissement_scolaire = "Lycée UEH"
        self.candidat.annee_obtention = 2024
        self.candidat.save()
        for type_document in (
            DocumentCandidat.TypeDocument.NAISSANCE,
            DocumentCandidat.TypeDocument.PHOTO,
            DocumentCandidat.TypeDocument.DIPLOME,
            DocumentCandidat.TypeDocument.NIF,
        ):
            DocumentCandidat.objects.create(
                candidat=self.candidat,
                type_document=type_document,
                fichier=f"tests/{type_document.lower()}.pdf",
            )
        EcoleCandidat.objects.create(
            candidat=self.candidat,
            nom="Lycée UEH",
            certificat="tests/certificat-scolaire.pdf",
        )

    def test_etapes_personnelles_sauvegardees_puis_adresse(self):
        self.utilisateur_candidat.prenom = "Marie"
        self.utilisateur_candidat.nom = "Jean"
        self.utilisateur_candidat.save(update_fields=["prenom", "nom"])
        self.client.force_login(self.utilisateur_candidat)
        fichiers = {
            "document_naissance": SimpleUploadedFile(
                "acte.pdf", b"%PDF-1.4", content_type="application/pdf"
            ),
            "photo_identite": SimpleUploadedFile(
                "photo.jpg", b"jpeg", content_type="image/jpeg"
            ),
            "document_nif": SimpleUploadedFile(
                "nif.pdf", b"%PDF-1.4", content_type="application/pdf"
            ),
        }
        donnees = {
            "etape": "1",
            "action": "suivant",
            "sexe": Candidat.Sexe.FEMININ,
            "date_naissance": "1990-01-15",
            "nationalite": "Haïtienne",
            "telephone": "+509 1234-5678",
            "nom_parent_responsable": "",
            "lieu_naissance": "Jacmel",
            "ninu": "",
            "nif": "0054438196",
        }

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                reponse = self.client.post(
                    reverse("candidats:mon_profil"), {**donnees, **fichiers}
                )

        self.assertRedirects(reponse, f"{reverse('candidats:mon_profil')}?etape=2")
        self.candidat.refresh_from_db()
        self.assertEqual(self.candidat.nif, "005-443-819-6")
        self.assertEqual(self.candidat.documents.count(), 3)

    def test_identifiant_personnel_est_nif_ou_ninu_pas_les_deux(self):
        self.utilisateur_candidat.prenom = "Marie"
        self.utilisateur_candidat.nom = "Jean"
        self.utilisateur_candidat.save(update_fields=["prenom", "nom"])
        self.client.force_login(self.utilisateur_candidat)
        fichiers = {
            "document_naissance": SimpleUploadedFile(
                "acte.pdf", b"%PDF-1.4", content_type="application/pdf"
            ),
            "photo_identite": SimpleUploadedFile(
                "photo.jpg", b"jpeg", content_type="image/jpeg"
            ),
            "document_nif": SimpleUploadedFile(
                "nif.pdf", b"%PDF-1.4", content_type="application/pdf"
            ),
            "document_ninu": SimpleUploadedFile(
                "ninu.pdf", b"%PDF-1.4", content_type="application/pdf"
            ),
        }
        reponse = self.client.post(
            reverse("candidats:mon_profil"),
            {
                "etape": "1",
                "sexe": Candidat.Sexe.FEMININ,
                "date_naissance": "1990-01-15",
                "nationalite": "Haïtienne",
                "telephone": "+509 1234-5678",
                "nom_parent_responsable": "",
                "lieu_naissance": "Jacmel",
                "nif": "000-000-000-0",
                "ninu": "123456789",
            }
            | fichiers,
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Saisissez le NIF ou le NINU, mais pas les deux")

    def test_remplacer_nif_par_ninu_retire_le_justificatif_nif_actif(self):
        self.utilisateur_candidat.prenom = "Marie"
        self.utilisateur_candidat.nom = "Jean"
        self.utilisateur_candidat.save(update_fields=["prenom", "nom"])
        self.candidat.sexe = Candidat.Sexe.FEMININ
        self.candidat.date_naissance = "1990-01-15"
        self.candidat.nationalite = "Haïtienne"
        self.candidat.telephone = "+509 1234-5678"
        self.candidat.lieu_naissance = "Jacmel"
        self.candidat.nif = "000-000-000-0"
        self.candidat.save()
        DocumentCandidat.objects.create(
            candidat=self.candidat,
            type_document=DocumentCandidat.TypeDocument.NAISSANCE,
            fichier="tests/acte.pdf",
        )
        DocumentCandidat.objects.create(
            candidat=self.candidat,
            type_document=DocumentCandidat.TypeDocument.PHOTO,
            fichier="tests/photo.jpg",
        )
        DocumentCandidat.objects.create(
            candidat=self.candidat,
            type_document=DocumentCandidat.TypeDocument.NIF,
            fichier="tests/nif.pdf",
        )
        self.client.force_login(self.utilisateur_candidat)
        fichier_ninu = SimpleUploadedFile(
            "ninu.pdf", b"%PDF-1.4", content_type="application/pdf"
        )

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                reponse = self.client.post(
                    reverse("candidats:mon_profil"),
                    {
                        "etape": "1",
                        "sexe": Candidat.Sexe.FEMININ,
                        "date_naissance": "1990-01-15",
                        "nationalite": "Haïtienne",
                        "telephone": "+509 1234-5678",
                        "nom_parent_responsable": "",
                        "lieu_naissance": "Jacmel",
                        "ninu": "123456789",
                        "nif": "",
                        "document_ninu": fichier_ninu,
                    },
                )

        self.assertRedirects(reponse, f"{reverse('candidats:mon_profil')}?etape=2")
        self.assertFalse(
            self.candidat.documents.filter(
                type_document=DocumentCandidat.TypeDocument.NIF
            ).exists()
        )
        self.assertTrue(
            self.candidat.documents.filter(
                type_document=DocumentCandidat.TypeDocument.NINU
            ).exists()
        )

    def test_etape_adresse_ne_peut_pas_etre_sautee(self):
        self.client.force_login(self.utilisateur_candidat)
        reponse = self.client.get(reverse("candidats:mon_profil"), {"etape": 2})
        self.assertRedirects(reponse, f"{reverse('candidats:mon_profil')}?etape=1")

    def test_communes_sont_filtrees_par_departement(self):
        self.client.force_login(self.utilisateur_candidat)
        reponse = self.client.get(
            reverse("candidats:communes"), {"departement": Candidat.Departement.NORD}
        )
        noms = {commune["value"] for commune in reponse.json()["communes"]}
        self.assertTrue(noms)
        self.assertNotIn("Port-au-Prince", noms)

    def test_commune_du_formulaire_adresse_depend_du_departement(self):
        self.preparer_etapes_precedentes()
        self.client.force_login(self.utilisateur_candidat)
        reponse = self.client.get(reverse("candidats:mon_profil"), {"etape": 2})
        choix = dict(reponse.context["formulaire"].fields["ville"].choices)
        self.assertIn("Port-au-Prince", choix)
        self.assertNotIn("Jacmel", choix)

    def test_ecole_et_certificat_sont_enregistres_avant_etudes(self):
        self.preparer_etapes_precedentes()
        self.client.force_login(self.utilisateur_candidat)
        certificat = SimpleUploadedFile(
            "certificat.pdf", b"%PDF-1.4", content_type="application/pdf"
        )

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                reponse = self.client.post(
                    reverse("candidats:mon_profil"),
                    {
                        "etape": "3",
                        "action": "suivant",
                        "nom": "Collège du Nord",
                        "zone": "Hinche",
                        "certificat": certificat,
                    },
                )

        self.assertRedirects(reponse, f"{reverse('candidats:mon_profil')}?etape=4")
        self.assertTrue(self.candidat.ecoles.filter(nom="Collège du Nord").exists())

    def test_etudes_superieures_peuvent_etre_omises_pour_terminer(self):
        self.preparer_etapes_precedentes()
        self.client.force_login(self.utilisateur_candidat)
        reponse = self.client.post(
            reverse("candidats:mon_profil"),
            {"etape": "4", "action": "terminer"},
        )
        self.assertRedirects(reponse, reverse("tableau_bord:mes_inscriptions"))
        self.assertFalse(self.candidat.parcours_etudes.exists())

    def test_etape_etudes_enregistre_un_parcours_et_ses_documents(self):
        self.preparer_etapes_precedentes()
        self.client.force_login(self.utilisateur_candidat)
        fichiers = {
            "certificat": SimpleUploadedFile(
                "releve.pdf", b"%PDF-1.4", content_type="application/pdf"
            ),
            "lettre_motivation": SimpleUploadedFile(
                "motivation.pdf", b"%PDF-1.4", content_type="application/pdf"
            ),
        }

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                reponse = self.client.post(
                    reverse("candidats:mon_profil"),
                    {
                        "etape": "4",
                        "action": "ajouter",
                        "etablissement": "Université UEH",
                        "niveau": "LICENCE",
                        "programme": "Sciences expérimentales",
                        "annee_obtention": "2024",
                        "type_document": "Relevé de notes",
                    }
                    | fichiers,
                )

        self.assertRedirects(reponse, f"{reverse('candidats:mon_profil')}?etape=4")
        parcours = self.candidat.parcours_etudes.get()
        self.assertEqual(parcours.etablissement, "Université UEH")
        self.assertTrue(parcours.certificat.name.endswith("releve.pdf"))
        self.assertTrue(parcours.lettre_motivation.name.endswith("motivation.pdf"))

    def test_nouvelle_inscription_reprend_la_premiere_etape_incomplete(self):
        self.client.force_login(self.utilisateur_candidat)
        reponse = self.client.get("/candidatures/nouvelle/")
        self.assertRedirects(reponse, f"{reverse('candidats:mon_profil')}?etape=1")
        self.assertTrue(self.client.session["reprendre_candidature"])
        self.assertFalse(
            BrouillonInscription.objects.filter(candidat=self.candidat).exists()
        )

    def test_nouvelle_inscription_reprend_a_adresse_si_personnel_est_termine(self):
        self.utilisateur_candidat.prenom = "Marie"
        self.utilisateur_candidat.nom = "Jean"
        self.utilisateur_candidat.save(update_fields=["prenom", "nom"])
        self.candidat.sexe = Candidat.Sexe.FEMININ
        self.candidat.date_naissance = "1990-01-15"
        self.candidat.nationalite = "Haïtienne"
        self.candidat.telephone = "509 1234-5678"
        self.candidat.lieu_naissance = "Jacmel"
        self.candidat.nif = "000-000-000-0"
        self.candidat.save()
        for type_document in (
            DocumentCandidat.TypeDocument.NAISSANCE,
            DocumentCandidat.TypeDocument.PHOTO,
            DocumentCandidat.TypeDocument.NIF,
        ):
            DocumentCandidat.objects.create(
                candidat=self.candidat,
                type_document=type_document,
                fichier=f"tests/{type_document.lower()}.pdf",
            )
        self.client.force_login(self.utilisateur_candidat)

        reponse = self.client.get("/candidatures/nouvelle/")

        self.assertRedirects(reponse, f"{reverse('candidats:mon_profil')}?etape=2")

    def test_brouillon_est_sauvegarde_et_recharge_a_la_reprise(self):
        self.preparer_etapes_precedentes()
        self.client.force_login(self.utilisateur_candidat)
        entite = Entite.objects.create(code="FSEA", nom="Sciences de l'éducation")
        option = Option.objects.create(entite=entite, nom="Pédagogie")
        HoraireEntite.objects.create(entite=entite, code=HoraireEntite.Code.AM)
        annee_attendue = f"{timezone.localdate().year}-{timezone.localdate().year + 1}"
        page = self.client.get("/candidatures/nouvelle/")
        self.assertEqual(page.status_code, 200)
        reponse_sauvegarde = self.client.post(
            reverse("candidatures:sauvegarder_brouillon"),
            {
                "entite": entite.pk,
                "option": option.pk,
                "horaire": "AM",
                "annee_academique": "1999-2000",
                "seq": "123456",
                "till": "654321",
                "date_depot": "2026-10-07",
            },
        )
        self.assertEqual(reponse_sauvegarde.status_code, 200)
        self.assertTrue(reponse_sauvegarde.json()["enregistre"])
        self.assertEqual(
            BrouillonInscription.objects.filter(candidat=self.candidat).count(), 1
        )
        self.assertEqual(
            BrouillonInscription.objects.get(candidat=self.candidat).annee_academique,
            annee_attendue,
        )
        brouillon = BrouillonInscription.objects.get(candidat=self.candidat)
        self.assertEqual((brouillon.seq, brouillon.till), ("123456", "654321"))

        reprise = self.client.get("/candidatures/nouvelle/")
        self.assertEqual(reprise.status_code, 200)
        self.assertEqual(reprise.context["formulaire"]["entite"].value(), entite.pk)
        self.assertEqual(
            reprise.context["formulaire"]["annee_academique"].value(), annee_attendue
        )
        self.assertEqual(reprise.context["formulaire"]["seq"].value(), "123456")
        self.assertEqual(reprise.context["formulaire"]["till"].value(), "654321")

        soumission = self.client.post(
            "/candidatures/nouvelle/",
            {
                "entite": entite.pk,
                "option": option.pk,
                "annee_academique": "1999-2000",
                "horaire": "AM",
                "seq": "123456",
                "till": "654321",
                "date_depot": "2026-10-07",
            },
        )
        self.assertEqual(soumission.status_code, 302)
        self.assertFalse(
            BrouillonInscription.objects.filter(candidat=self.candidat).exists()
        )
        self.assertEqual(
            Inscription.objects.filter(candidat=self.candidat)
            .order_by("-pk")
            .first()
            .annee_academique,
            annee_attendue,
        )
        inscription = Inscription.objects.get(candidat=self.candidat, entite=entite)
        self.assertEqual((inscription.seq, inscription.till), ("123456", "654321"))
        self.assertEqual(inscription.date_depot.isoformat(), "2026-10-07")

    def test_date_depot_reprise_de_la_derniere_inscription_si_brouillon_vide(self):
        self.preparer_etapes_precedentes()
        self.client.force_login(self.utilisateur_candidat)
        self.inscription_a.date_depot = timezone.localdate()
        self.inscription_a.save(update_fields=["date_depot"])

        reponse = self.client.get("/candidatures/nouvelle/")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            reponse.context["formulaire"]["date_depot"].value(),
            timezone.localdate(),
        )

    def test_detail_inscription_affiche_le_recapitulatif_complet_du_candidat(self):
        self.preparer_etapes_precedentes()
        self.client.force_login(self.utilisateur_candidat)

        reponse = self.client.get(
            reverse("candidatures:detail", args=[self.inscription_a.pk])
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            reponse.context["inscription"].candidat.etablissement_scolaire,
            "Lycée UEH",
        )
        self.assertContains(reponse, "Identité et coordonnées")
        self.assertContains(reponse, "Marie Jean")
        self.assertContains(reponse, self.utilisateur_candidat.email)
        self.assertContains(reponse, "Lycée UEH")
        self.assertContains(reponse, "Certificat de naissance")
        self.assertContains(
            reponse,
            reverse("documents:telecharger", args=[self.candidat.documents.first().pk]),
        )

    def test_admin_entite_ne_liste_que_ses_inscriptions(self):
        reponse = self.client.get("/gestion/inscriptions/")
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, str(self.inscription_a.numero_dossier))
        self.assertNotContains(reponse, str(self.inscription_b.numero_dossier))

    def test_journal_est_filtre_par_entite_et_par_type_action(self):
        action_locale = JournalAction.objects.create(
            utilisateur=self.admin_entite,
            inscription=self.inscription_a,
            entite=self.entite_a,
            action=JournalAction.Action.VALIDATION,
        )
        JournalAction.objects.create(
            utilisateur=self.admin_entite,
            inscription=self.inscription_b,
            entite=self.entite_b,
            action=JournalAction.Action.REJET,
            details={"motif": "Ne doit pas être visible"},
        )

        page = self.client.get(reverse("administration:journal_actions"))

        self.assertEqual(page.status_code, 200)
        self.assertEqual(list(page.context["actions"]), [action_locale])
        self.assertContains(page, str(self.inscription_a.numero_dossier))
        self.assertNotContains(page, str(self.inscription_b.numero_dossier))
        self.assertNotContains(page, "Ne doit pas être visible")
        filtre = self.client.get(
            reverse("administration:journal_actions"),
            {"action": JournalAction.Action.REJET},
        )
        self.assertEqual(list(filtre.context["actions"]), [])

    def test_admin_entite_est_renvoye_vers_l_interface_dediee(self):
        liste = self.client.get("/gestion/inscriptions/")
        self.assertEqual(liste.status_code, 200)
        self.assertContains(liste, str(self.inscription_a.numero_dossier))
        self.assertNotContains(liste, str(self.inscription_b.numero_dossier))
        url_modification = (
            f"/admin/candidatures/inscription/{self.inscription_b.pk}/change/"
        )
        url_suppression = (
            f"/admin/candidatures/inscription/{self.inscription_b.pk}/delete/"
        )
        self.assertRedirects(
            self.client.get(url_modification), "/gestion/inscriptions/"
        )
        self.assertRedirects(self.client.get(url_suppression), "/gestion/inscriptions/")
        self.assertRedirects(
            self.client.post(url_modification, {"entite": self.entite_a.pk}),
            "/gestion/inscriptions/",
        )
        self.assertRedirects(
            self.client.post(url_suppression, {"post": "yes"}),
            "/gestion/inscriptions/",
        )

    def test_gestion_salles_limitee_a_l_entite_autorisee(self):
        gestion = self.client.get("/gestion/salles/")
        self.assertEqual(gestion.status_code, 200)
        self.assertTrue(gestion.context["formulaire"].fields["entite"].widget.is_hidden)
        self.assertEqual(
            list(gestion.context["formulaire"].fields["entite"].queryset),
            [self.entite_a],
        )
        reponse_interdite = self.client.post(
            "/gestion/salles/",
            {"entite": self.entite_b.pk, "nom": "Salle interdite", "capacite": 20},
        )
        self.assertEqual(reponse_interdite.status_code, 400)
        self.assertFalse(Salle.objects.filter(nom="Salle interdite").exists())

    def test_superuser_ne_voit_que_les_salles_de_l_entite_du_dossier(self):
        salle_a = Salle.objects.create(entite=self.entite_a, nom="Salle entité A")
        Salle.objects.create(entite=self.entite_b, nom="Salle entité B")
        superutilisateur = Utilisateur.objects.create_superuser(
            "super-salles@example.com", "MotDePasse-Securise-2026"
        )
        self.client.force_login(superutilisateur)

        reponse = self.client.get(
            f"/admin/candidatures/inscription/{self.inscription_a.pk}/change/"
        )

        self.assertEqual(reponse.status_code, 200)
        salles = reponse.context["adminform"].form.fields["salle"].queryset
        self.assertEqual(list(salles), [salle_a])

    def test_superuser_peut_modifier_le_statut_et_la_modification_est_journalisee(self):
        url = f"/admin/candidatures/inscription/{self.inscription_a.pk}/change/"
        self.client.force_login(self.admin_entite)
        page_admin_entite = self.client.get(url)
        self.assertRedirects(page_admin_entite, "/gestion/inscriptions/")

        superutilisateur = Utilisateur.objects.create_superuser(
            "super-statut@example.com", "MotDePasse-Securise-2026"
        )
        self.client.force_login(superutilisateur)
        page_superuser = self.client.get(url)
        self.assertEqual(page_superuser.status_code, 200)
        self.assertContains(page_superuser, '<select name="statut"', html=False)
        reponse = self.client.post(
            url,
            {
                "entite": self.entite_a.pk,
                "option": "",
                "annee_academique": "2026-2027",
                "horaire": "",
                "seq": "",
                "till": "",
                "date_depot": "",
                "recu_paiement": "",
                "salle": "",
                "statut": Inscription.Statut.VALIDE,
                "_save": "Enregistrer",
            },
        )
        self.assertEqual(reponse.status_code, 302)
        self.inscription_a.refresh_from_db()
        self.assertEqual(self.inscription_a.statut, Inscription.Statut.VALIDE)
        self.assertTrue(
            JournalAction.objects.filter(
                utilisateur=superutilisateur,
                inscription=self.inscription_a,
                action=JournalAction.Action.MODIFICATION_STATUT,
                details={
                    "ancien_statut": Inscription.Statut.EN_ATTENTE,
                    "nouveau_statut": Inscription.Statut.VALIDE,
                },
            ).exists()
        )

    def test_admin_entite_ne_peut_pas_ouvrir_une_option_d_une_autre_entite(self):
        from applications.entites.models import Option

        option = Option.objects.create(entite=self.entite_b, nom="Droit")
        self.assertEqual(
            self.client.get(f"/admin/entites/option/{option.pk}/change/").status_code,
            302,
        )
        self.assertEqual(
            self.client.get(f"/gestion/options/?modifier={option.pk}").status_code,
            404,
        )

    def test_admin_entite_ne_peut_ni_valider_ni_telecharger_ni_exporter_autrui(self):
        url_validation = f"/gestion/inscriptions/{self.inscription_b.pk}/valider/"
        self.assertEqual(self.client.post(url_validation).status_code, 404)
        self.assertEqual(
            self.client.get(f"/candidatures/{self.inscription_b.pk}/pdf/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/candidatures/{self.inscription_b.pk}/recu/").status_code,
            404,
        )
        export = self.client.get("/gestion/inscriptions/exporter/")
        self.assertEqual(export.status_code, 200)
        contenu = export.content.decode("utf-8-sig")
        self.assertIn(str(self.inscription_a.numero_dossier), contenu)
        self.assertNotIn(str(self.inscription_b.numero_dossier), contenu)

    def test_affectation_de_salle_est_liee_a_l_entite(self):
        salle_a = Salle.objects.create(entite=self.entite_a, nom="Salle 1", capacite=40)
        salle_b = Salle.objects.create(entite=self.entite_b, nom="Salle 2", capacite=30)
        url = f"/gestion/inscriptions/{self.inscription_a.pk}/salle/"
        reponse = self.client.post(url, {"salle": salle_a.pk})
        self.assertEqual(reponse.status_code, 200)
        self.inscription_a.refresh_from_db()
        self.assertEqual(self.inscription_a.salle_id, salle_a.pk)
        self.assertTrue(
            JournalAction.objects.filter(
                inscription=self.inscription_a,
                action=JournalAction.Action.AFFECTATION_SALLE,
            ).exists()
        )
        self.assertEqual(self.client.post(url, {"salle": salle_b.pk}).status_code, 400)
        self.inscription_a.refresh_from_db()
        self.assertEqual(self.inscription_a.salle_id, salle_a.pk)

    def test_api_filtre_les_inscriptions_par_entite(self):
        reponse = self.client.get("/api/inscriptions/")
        self.assertEqual(reponse.status_code, 200)
        numeros = [ligne["numero_dossier"] for ligne in reponse.json()]
        self.assertIn(self.inscription_a.numero_dossier, numeros)
        self.assertNotIn(self.inscription_b.numero_dossier, numeros)

    def test_admin_entite_ne_peut_pas_deplacer_son_inscription(self):
        url = f"/admin/candidatures/inscription/{self.inscription_a.pk}/change/"
        reponse = self.client.post(
            url,
            {
                "entite": self.entite_b.pk,
                "option": "",
                "annee_academique": "2026-2027",
                "horaire": "",
                "salle": "",
            },
        )
        self.assertRedirects(reponse, "/gestion/inscriptions/")
        self.inscription_a.refresh_from_db()
        self.assertEqual(self.inscription_a.entite_id, self.entite_a.pk)

    def test_validation_rejet_et_suppression_sont_journalises(self):
        reponse = self.client.post(
            f"/gestion/inscriptions/{self.inscription_a.pk}/valider/"
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(
            JournalAction.objects.filter(
                inscription=self.inscription_a,
                action=JournalAction.Action.VALIDATION,
                utilisateur=self.admin_entite,
            ).exists()
        )
        reponse = self.client.post(
            f"/gestion/inscriptions/{self.inscription_a.pk}/rejeter/",
            {"motif": "Dossier incomplet"},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(
            JournalAction.objects.filter(
                inscription=self.inscription_a,
                action=JournalAction.Action.REJET,
            ).exists()
        )
        reponse = self.client.post(
            f"/gestion/inscriptions/{self.inscription_a.pk}/supprimer/",
        )
        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(
            JournalAction.objects.filter(
                entite=self.entite_a,
                action=JournalAction.Action.SUPPRESSION,
            ).exists()
        )

    def test_superutilisateur_accede_a_toutes_les_entites(self):
        superutilisateur = Utilisateur.objects.create_superuser(
            "super@example.com", "MotDePasse-Securise-2026"
        )
        self.client.force_login(superutilisateur)
        liste = self.client.get("/gestion/inscriptions/")
        self.assertContains(liste, str(self.inscription_a.numero_dossier))
        self.assertContains(liste, str(self.inscription_b.numero_dossier))
        self.assertEqual(
            self.client.get(f"/candidatures/{self.inscription_b.pk}/pdf/").status_code,
            200,
        )

    def test_liste_candidats_exclut_les_comptes_administrateurs(self):
        Candidat.objects.create(utilisateur=self.admin_entite)
        superutilisateur = Utilisateur.objects.create_superuser(
            "super-candidats@example.com", "MotDePasse-Securise-2026"
        )
        Candidat.objects.create(utilisateur=superutilisateur)
        self.client.force_login(superutilisateur)

        reponse = self.client.get("/admin/candidats/candidat/")

        self.assertEqual(reponse.status_code, 200)
        candidats_affiches = reponse.context["cl"].result_list
        self.assertEqual(
            {candidat.pk for candidat in candidats_affiches}, {self.candidat.pk}
        )

    def test_soumission_envoie_un_courriel_avec_le_pdf(self):
        self.preparer_etapes_precedentes()
        self.client.force_login(self.utilisateur_candidat)
        entite = Entite.objects.create(code="FSEA", nom="Sciences de l'éducation")
        option = Option.objects.create(entite=entite, nom="Pédagogie")
        HoraireEntite.objects.create(entite=entite, code=HoraireEntite.Code.AM)
        mail.outbox.clear()
        reponse = self.client.post(
            "/candidatures/nouvelle/",
            {
                "entite": entite.pk,
                "option": option.pk,
                "annee_academique": "2026-2027",
                "horaire": "AM",
            },
        )
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        pieces_jointes = mail.outbox[0].attachments
        self.assertEqual(pieces_jointes[0][2], "application/pdf")
        self.assertTrue(pieces_jointes[0][1].startswith(b"%PDF"))
        self.assertGreaterEqual(pieces_jointes[0][1].count(b"/Subtype /Image"), 2)

    def test_recu_de_paiement_est_lie_et_telecharge_depuis_le_dossier(self):
        self.preparer_etapes_precedentes()
        self.client.force_login(self.utilisateur_candidat)
        entite = Entite.objects.create(code="FSEA", nom="Sciences de l'éducation")
        option = Option.objects.create(entite=entite, nom="Pédagogie")
        HoraireEntite.objects.create(entite=entite, code=HoraireEntite.Code.AM)
        contenu_recu = b"preuve de paiement"

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                reponse = self.client.post(
                    "/candidatures/nouvelle/",
                    {
                        "entite": entite.pk,
                        "option": option.pk,
                        "annee_academique": "2026-2027",
                        "horaire": "AM",
                        "recu_paiement": SimpleUploadedFile(
                            "recu.pdf", contenu_recu, content_type="application/pdf"
                        ),
                    },
                )
                self.assertEqual(reponse.status_code, 302)
                inscription = Inscription.objects.get(
                    candidat=self.candidat, entite=entite
                )
                telechargement = self.client.get(
                    reverse(
                        "candidatures:telecharger_recu_paiement",
                        args=[inscription.pk],
                    )
                )
                self.assertEqual(telechargement.status_code, 200)
                self.assertEqual(
                    b"".join(telechargement.streaming_content), contenu_recu
                )

    def test_candidat_voit_ses_inscriptions_courantes_et_precedentes(self):
        entite_precedente = Entite.objects.create(
            code="FSEA", nom="Sciences de l'éducation"
        )
        ancienne = Inscription.objects.create(
            candidat=self.candidat,
            entite=entite_precedente,
            annee_academique="2025-2026",
        )
        self.client.force_login(self.utilisateur_candidat)
        reponse = self.client.get(reverse("tableau_bord:mes_inscriptions"))
        self.assertEqual(reponse.status_code, 200, reponse.content.decode()[:500])
        self.assertEqual(reponse.context["nb_total"], 3)
        self.assertEqual(list(reponse.context["inscriptions_precedentes"]), [ancienne])
        self.assertCountEqual(
            reponse.context["inscriptions"],
            [self.inscription_a, self.inscription_b],
        )
        autre_utilisateur = Utilisateur.objects.create_user(
            "candidat-tiers@example.com", "MotDePasse-Securise-2026"
        )
        autre_candidat = Candidat.objects.create(utilisateur=autre_utilisateur)
        inscription_tiers = Inscription.objects.create(
            candidat=autre_candidat,
            entite=self.entite_b,
            annee_academique="2026-2027",
        )
        self.assertEqual(
            self.client.get(
                reverse("candidatures:detail", args=[inscription_tiers.pk])
            ).status_code,
            404,
        )

    def test_compte_gp7_sans_profil_candidat_ne_peut_pas_ouvrir_son_tableau(self):
        utilisateur = Utilisateur.objects.create_user(
            "sans-profil@example.com", "MotDePasse-Securise-2026"
        )
        self.client.force_login(utilisateur)
        reponse = self.client.get(reverse("tableau_bord:mes_inscriptions"))
        self.assertEqual(reponse.status_code, 403)
        self.assertContains(
            reponse,
            "Cette page est réservée aux candidats",
            status_code=403,
        )
        self.assertFalse(Candidat.objects.filter(utilisateur=utilisateur).exists())

    def test_administrateurs_sans_profil_candidat_sont_rediriges_vers_leur_espace(self):
        superutilisateur = Utilisateur.objects.create_superuser(
            "super-sans-profil@example.com", "MotDePasse-Securise-2026"
        )
        self.client.force_login(superutilisateur)
        self.assertRedirects(
            self.client.get(reverse("tableau_bord:mes_inscriptions")), "/admin/"
        )

        administrateur = Utilisateur.objects.create_user(
            "admin-sans-profil@example.com",
            "MotDePasse-Securise-2026",
            is_staff=True,
        )
        AdministrateurEntite.objects.create(
            utilisateur=administrateur, entite=self.entite_a
        )
        self.client.force_login(administrateur)
        self.assertRedirects(
            self.client.get(reverse("tableau_bord:mes_inscriptions")),
            reverse("administration:liste_inscriptions"),
        )

    def test_admin_entite_a_son_profil_sans_acces_au_profil_candidat(self):
        self.assertRedirects(
            self.client.get("/admin/entites/salle/add/"),
            reverse("administration:liste_inscriptions"),
        )
        reponse_profil = self.client.get(reverse("candidats:mon_profil"))
        reponse_documents = self.client.get(reverse("documents:mes_documents"))
        self.assertEqual(reponse_profil.status_code, 302)
        self.assertEqual(
            reponse_profil.url, reverse("tableau_bord:mes_inscriptions")
        )
        self.assertEqual(reponse_documents.status_code, 302)
        self.assertEqual(
            reponse_documents.url, reverse("tableau_bord:mes_inscriptions")
        )

        page = self.client.get(reverse("administration:liste_inscriptions"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "ESPACE ADMINISTRATION")
        self.assertContains(page, reverse("administration:liste_inscriptions"))
        self.assertContains(page, reverse("comptes:profil_administrateur"))
        self.assertNotContains(page, f'href="{reverse("candidats:mon_profil")}"')
        self.assertNotContains(page, f'href="{reverse("documents:mes_documents")}"')
        self.assertNotContains(page, reverse("candidats:photo_identite"))

    def test_personnel_gp7_est_admin_admission_si_le_code_entite_correspond(self):
        entite_gp7 = EntiteGP7.objects.create(
            code="FDS",
            nom="Faculté des Sciences",
            regime=EntiteGP7.Regime.CREDITS,
        )
        personnel = Utilisateur.objects.create_user(
            "personnel-fds@example.com",
            "MotDePasse-Securise-2026",
            role=Utilisateur.Role.PERSONNEL,
            entite=entite_gp7,
        )
        autre_entite_gp7 = EntiteGP7.objects.create(
            code="AUTRE",
            nom="Autre entité GP7",
            regime=EntiteGP7.Regime.CREDITS,
        )
        personnel_autre_entite = Utilisateur.objects.create_user(
            "personnel-autre@example.com",
            "MotDePasse-Securise-2026",
            role=Utilisateur.Role.PERSONNEL,
            entite=autre_entite_gp7,
        )

        self.assertFalse(personnel_autre_entite.est_administrateur_entite)
        self.client.force_login(personnel)

        self.assertTrue(personnel.est_administrateur_entite)
        self.assertEqual(
            self.client.get(reverse("administration:liste_inscriptions")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("comptes:profil_administrateur")).status_code,
            200,
        )

    def test_compte_gp7_sans_profil_candidat_ne_peut_pas_deposer(self):
        utilisateur_gp7 = Utilisateur.objects.create_user(
            "etudiant-gp7@example.com",
            "MotDePasse-Securise-2026",
        )
        self.client.force_login(utilisateur_gp7)

        reponse_espace = self.client.get(reverse("tableau_bord:mes_inscriptions"))
        reponse_demande = self.client.get(reverse("candidatures:creer"))

        self.assertEqual(reponse_espace.status_code, 403)
        self.assertContains(
            reponse_espace,
            "Cette page est réservée aux candidats",
            status_code=403,
        )
        self.assertNotContains(
            reponse_espace,
            "No Candidat matches",
            status_code=403,
        )
        self.assertEqual(reponse_demande.status_code, 403)
        self.assertContains(
            reponse_demande,
            "Cette page est réservée aux candidats",
            status_code=403,
        )
        self.assertFalse(Candidat.objects.filter(utilisateur=utilisateur_gp7).exists())

    def test_admin_entite_peut_modifier_son_profil_et_sa_photo_privee(self):
        with TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root
        ):
            page = self.client.get(reverse("comptes:profil_administrateur"))
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, reverse("account_change_password"))
            self.assertContains(page, "data-apercu-photo-profil")
            self.assertContains(page, "/static/js/apercu-photo-profil.js")

            reponse = self.client.post(
                reverse("comptes:profil_administrateur"),
                {
                    "prenom": "Nadia",
                    "nom": "Baptiste",
                    "photo_profil": SimpleUploadedFile(
                        "profil.png",
                        b"photo",
                        content_type="image/png",
                    ),
                },
            )

            self.assertRedirects(reponse, reverse("comptes:profil_administrateur"))
            self.admin_entite.refresh_from_db()
            self.assertEqual(self.admin_entite.get_full_name(), "Nadia Baptiste")
            self.assertTrue(self.admin_entite.photo_profil)

            photo = self.client.get(reverse("comptes:photo_profil"))
            self.assertEqual(photo.status_code, 200)
            self.assertEqual(photo["Cache-Control"], "private, no-store")
            photo.close()

            self.client.force_login(self.utilisateur_candidat)
            self.assertEqual(
                self.client.get(reverse("comptes:photo_profil")).status_code, 403
            )

    def test_utilisateur_connecte_peut_revenir_a_l_accueil_sans_deconnexion(self):
        self.client.force_login(self.utilisateur_candidat)
        reponse = self.client.get("/")
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Accueil")
        self.assertContains(reponse, "Mon espace candidat")
        self.assertContains(reponse, "modal-confirmation-deconnexion")
        self.assertContains(reponse, "data-confirmation-deconnexion")
        self.assertContains(reponse, "/static/js/confirmation-deconnexion.js")

    def test_panneau_utilise_le_logo_et_la_photo_privee_du_candidat(self):
        self.client.force_login(self.utilisateur_candidat)
        page = self.client.get(reverse("candidats:mon_profil"))
        self.assertContains(page, "/static/images/logo.png")
        self.assertContains(page, "/static/js/avatar-utilisateur.js")
        self.assertContains(page, "avatar-initial")
        self.assertContains(page, reverse("candidats:photo_identite"))

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                DocumentCandidat.objects.create(
                    candidat=self.candidat,
                    type_document=DocumentCandidat.TypeDocument.PHOTO,
                    fichier=SimpleUploadedFile(
                        "photo.jpg", b"jpeg", content_type="image/jpeg"
                    ),
                )
                reponse = self.client.get(reverse("candidats:photo_identite"))
                self.assertEqual(reponse.status_code, 200)
                self.assertEqual(reponse["Content-Type"], "image/jpeg")
                self.assertEqual(reponse["Cache-Control"], "private, no-store")
                reponse.close()

    def test_guide_documents_et_navigation_mobile_sont_accessibles(self):
        self.client.force_login(self.utilisateur_candidat)
        reponse = self.client.get(reverse("tableau_bord:guide_documents"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Numéro d’Immatriculation Fiscale")
        self.assertContains(reponse, "validation définitive en présentiel")
        self.assertContains(reponse, "2 Mo par document")
        self.assertContains(reponse, "navigation-basse-mobile")
        self.assertContains(reponse, 'data-view="guide_documents"')
        self.assertContains(reponse, 'data-navigation="guide"')
        self.assertContains(reponse, "data-ouvrir-plus")
        self.assertContains(reponse, "Se déconnecter")

    def test_creation_de_compte_allauth_provisionne_le_profil_candidat(self):
        self.client.logout()
        page_inscription = self.client.get("/comptes/signup/")
        self.assertEqual(page_inscription.status_code, 200)
        self.assertContains(page_inscription, "Prénom")
        self.assertContains(page_inscription, "Nom")
        reponse = self.client.post(
            "/comptes/signup/",
            {
                "email": "nouveau-candidat@example.com",
                "prenom": "Marie",
                "nom": "Jean",
                "password1": "MotDePasse-Securise-2026",
                "password2": "MotDePasse-Securise-2026",
            },
        )
        self.assertEqual(reponse.status_code, 302)
        utilisateur = Utilisateur.objects.get(email="nouveau-candidat@example.com")
        self.assertEqual(utilisateur.prenom, "Marie")
        self.assertEqual(utilisateur.nom, "Jean")
        self.assertTrue(Candidat.objects.filter(utilisateur=utilisateur).exists())
        self.assertTrue(mail.outbox)
        self.assertIn("confirmer", mail.outbox[-1].body.lower())
        lien_confirmation = (
            re.search(r"https?://[^\s<>]+", mail.outbox[-1].body).group(0).rstrip(".,)")
        )
        chemin_confirmation = urlsplit(lien_confirmation).path
        page_confirmation = self.client.get(chemin_confirmation)
        self.assertEqual(page_confirmation.status_code, 200)
        reponse_confirmation = self.client.post(chemin_confirmation)
        self.assertRedirects(reponse_confirmation, reverse("account_login"))

    def test_redirection_login_requise_utilise_le_prefixe_comptes(self):
        self.client.logout()
        reponse = self.client.get(reverse("tableau_bord:mes_inscriptions"))
        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(reponse.url.startswith(reverse("comptes:connexion")))

    def test_page_verification_email_herite_du_portail(self):
        reponse = self.client.get("/comptes/confirm-email/")
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Vérifiez votre adresse e-mail")
        self.assertContains(reponse, "static/css/auth.css")
        self.assertContains(reponse, "static/css/style_admission.css")

    def test_visiteur_anonyme_consulte_l_accueil_public_et_ses_rubriques(self):
        self.client.logout()
        reponse = self.client.get("/")
        self.assertEqual(reponse.status_code, 200)
        for rubrique in (
            "Accueil",
            "Guide du postulant",
            "Entités",
            "Statistiques",
            "À propos",
        ):
            with self.subTest(rubrique=rubrique):
                self.assertContains(reponse, rubrique)
        self.assertContains(reponse, self.entite_a.nom)
        self.assertEqual(reponse.context["nb_entites"], 2)
        self.assertContains(reponse, "/static/images/logo.png")
        self.assertContains(reponse, "navigation-basse-mobile")
        self.assertContains(reponse, "data-ouvrir-plus")
        self.assertContains(reponse, "navigation-publique.js")
        self.assertContains(reponse, "panneau-plus")
        self.assertContains(reponse, "À propos")
        self.assertNotContains(reponse, "bouton-menu-public")

    def test_rubriques_publiques_ont_chacune_leur_page(self):
        self.client.logout()
        rubriques = (
            ("guide_public", "guide", ("entites", "statistiques", "a-propos")),
            ("entites_publiques", "entites", ("guide", "statistiques", "a-propos")),
            (
                "statistiques_publiques",
                "statistiques",
                ("guide", "entites", "a-propos"),
            ),
            ("a_propos_public", "a-propos", ("guide", "entites", "statistiques")),
        )
        for nom_url, section, autres_sections in rubriques:
            with self.subTest(rubrique=section):
                reponse = self.client.get(reverse(f"tableau_bord:{nom_url}"))
                self.assertEqual(reponse.status_code, 200)
                self.assertContains(reponse, f'id="{section}"', html=False)
                for autre_section in autres_sections:
                    self.assertNotContains(reponse, f'id="{autre_section}"', html=False)

    def test_superadmin_peut_selectionner_un_candidat_a_la_creation(self):
        superutilisateur = Utilisateur.objects.create_superuser(
            "superadmin-inscription@example.com", "MotDePasse-Securise-2026"
        )
        self.client.force_login(superutilisateur)

        page = self.client.get(reverse("admin:candidatures_inscription_add"))

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'name="candidat"', html=False)

    def test_graphiques_statistiques_reflètent_les_inscriptions_sans_données_personnelles(
        self,
    ):
        self.candidat.sexe = Candidat.Sexe.FEMININ
        self.candidat.departement_geographique = Candidat.Departement.NORD
        self.candidat.save(update_fields=["sexe", "departement_geographique"])
        reponse = self.client.get("/")
        donnees = reponse.context["donnees_statistiques"]
        entites = dict(zip(donnees["entites"]["labels"], donnees["entites"]["valeurs"]))
        sexes = dict(zip(donnees["sexe"]["labels"], donnees["sexe"]["valeurs"]))
        departements = dict(
            zip(donnees["departements"]["labels"], donnees["departements"]["valeurs"])
        )
        self.assertEqual(reponse.context["nb_inscriptions"], 2)
        self.assertEqual(reponse.context["nb_entites"], 2)
        self.assertEqual(entites["FDS"], 1)
        self.assertEqual(entites["FASCH"], 1)
        self.assertEqual(sexes["Féminin"], 2)
        self.assertEqual(departements["Nord"], 2)
        self.assertEqual(len(donnees["evolution"]["labels"]), 30)
        self.assertEqual(sum(donnees["evolution"]["valeurs"]), 2)
        self.assertNotIn(self.utilisateur_candidat.email, str(donnees))

    def test_profil_affiche_les_champs_et_documents_d_identite(self):
        self.client.force_login(self.utilisateur_candidat)
        formulaire_personnel = InformationsPersonnellesForm(
            utilisateur=self.utilisateur_candidat
        )
        communes = formulaire_personnel.fields["lieu_naissance"].choices[1:]
        reponse = self.client.get("/candidats/mon-profil/")
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Genre")
        self.assertContains(reponse, "Nationalité")
        self.assertContains(reponse, "NINU")
        self.assertContains(reponse, "Document NINU")
        self.assertContains(reponse, "Document NIF")
        self.assertContains(reponse, "Acte de naissance")
        self.assertContains(reponse, "Photo d’identité")
        self.assertContains(reponse, "Suivant : Informations d’Adresse")
        self.assertEqual(len(communes), 148)
        self.assertIn(("Jacmel", "Jacmel (Sud-Est)"), communes)
        self.assertIn(("Port-au-Prince", "Port-au-Prince (Ouest)"), communes)

    def test_profil_enregistre_les_identifiants_et_pieces_televersees(self):
        self.utilisateur_candidat.prenom = "Marie"
        self.utilisateur_candidat.nom = "Jean"
        self.utilisateur_candidat.save(update_fields=["prenom", "nom"])
        lieu_naissance = (
            ProfilCandidatForm(utilisateur=self.utilisateur_candidat)
            .fields["lieu_naissance"]
            .choices[1][0]
        )
        fichiers = {
            "document_naissance": SimpleUploadedFile(
                "acte.pdf", b"%PDF-1.4", content_type="application/pdf"
            ),
            "photo_identite": SimpleUploadedFile(
                "photo.jpg", b"jpeg", content_type="image/jpeg"
            ),
            "document_nif": SimpleUploadedFile(
                "nif.pdf", b"%PDF-1.4", content_type="application/pdf"
            ),
        }
        donnees = {
            "nationalite": "Haïtienne",
            "telephone": "+509 1234-5678",
            "date_naissance": "1990-01-15",
            "lieu_naissance": lieu_naissance,
            "nom_parent_responsable": "",
            "nif": "000-000-000-0",
            "ninu": "",
            "adresse": "Rue de la Paix",
            "ville": "Port-au-Prince",
            "sexe": Candidat.Sexe.FEMININ,
            "departement_geographique": Candidat.Departement.OUEST,
            "etablissement_scolaire": "Lycée UEH",
            "annee_obtention": "2010",
        }

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                formulaire = ProfilCandidatForm(
                    data=donnees,
                    files=fichiers,
                    instance=self.candidat,
                    utilisateur=self.utilisateur_candidat,
                )
                self.assertTrue(formulaire.is_valid(), formulaire.errors)
                formulaire.save()

        self.candidat.refresh_from_db()
        self.assertEqual(self.candidat.nif, "000-000-000-0")
        self.assertEqual(self.candidat.nationalite, "Haïtienne")
        self.assertTrue(
            self.candidat.documents.filter(
                type_document=DocumentCandidat.TypeDocument.NAISSANCE
            ).exists()
        )
        self.assertTrue(
            self.candidat.documents.filter(
                type_document=DocumentCandidat.TypeDocument.PHOTO
            ).exists()
        )
        self.assertTrue(
            self.candidat.documents.filter(
                type_document=DocumentCandidat.TypeDocument.NIF
            ).exists()
        )

    def test_profil_mineur_exige_un_identifiant_et_un_responsable(self):
        self.utilisateur_candidat.prenom = "Jean"
        self.utilisateur_candidat.nom = "Pierre"
        formulaire = ProfilCandidatForm(
            data={
                "nationalite": "Haïtienne",
                "telephone": "509 1234-5678",
                "date_naissance": "2012-01-15",
                "lieu_naissance": "Port-au-Prince",
                "nom_parent_responsable": "",
                "nif": "",
                "ninu": "",
                "adresse": "Rue de la Paix",
                "ville": "Port-au-Prince",
                "sexe": Candidat.Sexe.MASCULIN,
                "departement_geographique": "",
                "etablissement_scolaire": "Lycée UEH",
                "annee_obtention": "2024",
            },
            instance=self.candidat,
            utilisateur=self.utilisateur_candidat,
        )

        self.assertFalse(formulaire.is_valid())
        self.assertIn("nif", formulaire.errors)
        self.assertIn("nom_parent_responsable", formulaire.errors)

    def test_entite_fermee_est_visible_mais_aucune_inscription_est_acceptee(self):
        self.entite_a.inscription_ouverte = False
        self.entite_a.save(update_fields=["inscription_ouverte"])
        self.client.logout()
        page_publique = self.client.get("/")
        self.assertContains(page_publique, "Inscriptions fermées")
        for nom_url in (
            "accueil",
            "guide_public",
            "entites_publiques",
            "statistiques_publiques",
            "a_propos_public",
        ):
            with self.subTest(nom_url=nom_url):
                self.assertContains(
                    page_publique,
                    f'href="{reverse(f"tableau_bord:{nom_url}")}"',
                )
        self.client.force_login(self.utilisateur_candidat)
        self.preparer_etapes_precedentes()
        reponse = self.client.post(
            "/candidatures/nouvelle/",
            {
                "entite": self.entite_a.pk,
                "option": "",
                "annee_academique": "2026-2027",
                "horaire": "",
            },
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertContains(reponse, "Les inscriptions sont fermées", status_code=400)
        self.assertFalse(
            Inscription.objects.filter(candidat=self.candidat, entite=self.entite_a)
            .exclude(pk=self.inscription_a.pk)
            .exists()
        )
        with self.assertRaises(ValidationError):
            Inscription.objects.create(
                candidat=self.candidat,
                entite=self.entite_a,
                annee_academique="2026-2027",
            )
        self.assertEqual(
            self.client.get(
                "/candidatures/choix-entite/", {"entite": self.entite_a.pk}
            ).status_code,
            404,
        )

    def test_connexion_et_inscription_utilisent_les_gabarits_du_portail(self):
        self.client.logout()
        for url in ("/comptes/login/", "/comptes/signup/"):
            with self.subTest(url=url):
                reponse = self.client.get(url)
                self.assertEqual(reponse.status_code, 200)
                self.assertContains(reponse, "formulaire-auth")
                self.assertContains(reponse, "/static/css/style_admission.css")
                self.assertContains(reponse, "/static/css/auth.css")
                self.assertContains(reponse, "/static/js/visibilite-mot-de-passe.js")
                self.assertContains(reponse, "auth-page-focus")
                self.assertContains(reponse, "/static/js/focus-champ-auth.js")

    def test_admin_charge_le_controle_de_visibilite_du_mot_de_passe(self):
        self.client.logout()
        reponse = self.client.get("/admin/login/")
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "/static/js/visibilite-mot-de-passe.js")
        self.assertContains(reponse, "/static/css/password-visibility.css")

    def test_attribution_admin_entite_confirme_le_courriel(self):
        superutilisateur = Utilisateur.objects.create_superuser(
            "super-attribution@example.com", "MotDePasse-Securise-2026"
        )
        utilisateur = Utilisateur.objects.create_user(
            "admin-entite-cree@example.com",
            "MotDePasse-Securise-2026",
            is_staff=True,
        )
        adresse = EmailAddress.objects.create(
            user=utilisateur,
            email=utilisateur.email,
            primary=False,
            verified=False,
        )
        self.client.force_login(superutilisateur)

        reponse = self.client.post(
            reverse("admin:entites_administrateurentite_add"),
            {
                "utilisateur": utilisateur.pk,
                "entite": self.entite_a.pk,
                "_save": "Enregistrer",
            },
        )

        self.assertEqual(reponse.status_code, 302)
        adresse.refresh_from_db()
        self.assertTrue(adresse.primary)
        self.assertTrue(adresse.verified)
        utilisateur.refresh_from_db()
        self.assertFalse(utilisateur.is_staff)

    def test_creation_admin_confirme_automatiquement_le_courriel(self):
        superutilisateur = Utilisateur.objects.create_superuser(
            "super-creation@example.com", "MotDePasse-Securise-2026"
        )
        self.client.force_login(superutilisateur)
        mail.outbox.clear()

        reponse = self.client.post(
            reverse("admin:comptes_utilisateur_add"),
            {
                "email": "admin-cree@example.com",
                "prenom": "Admin",
                "nom": "Local",
                "mot_de_passe": "MotDePasse-Securise-2026",
                "confirmation_mot_de_passe": "MotDePasse-Securise-2026",
                "is_staff": "on",
                "is_active": "on",
                "_save": "Enregistrer",
            },
        )

        self.assertEqual(reponse.status_code, 302)
        utilisateur = Utilisateur.objects.get(email="admin-cree@example.com")
        adresse = EmailAddress.objects.get(user=utilisateur, email=utilisateur.email)
        self.assertTrue(adresse.primary)
        self.assertTrue(adresse.verified)
        self.assertEqual(mail.outbox, [])

    def test_reinitialisation_complete_du_mot_de_passe_par_email(self):
        EmailAddress.objects.create(
            user=self.utilisateur_candidat,
            email=self.utilisateur_candidat.email,
            primary=True,
            verified=True,
        )
        mail.outbox.clear()
        reponse = self.client.get(reverse("account_reset_password"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Mot de passe oublié ?")
        reponse = self.client.post(
            reverse("account_reset_password"),
            {"email": self.utilisateur_candidat.email},
        )
        self.assertRedirects(reponse, reverse("account_reset_password_done"))
        self.assertEqual(len(mail.outbox), 1)
        page_envoi = self.client.get(reverse("account_reset_password_done"))
        self.assertContains(page_envoi, "Vérifiez votre boîte e-mail")

        chemin_invalide = reverse(
            "account_reset_password_from_key",
            kwargs={"uidb36": "invalide", "key": "cle-expiree"},
        )
        page_invalide = self.client.get(chemin_invalide)
        self.assertEqual(page_invalide.status_code, 200)
        self.assertContains(page_invalide, "Ce lien ne fonctionne plus")

        lien = (
            re.search(r"https?://[^\s<>]+", mail.outbox[0].body).group(0).rstrip(".,)")
        )
        chemin = urlsplit(lien).path
        page_reinitialisation = self.client.get(chemin, follow=True)
        self.assertEqual(page_reinitialisation.status_code, 200)
        self.assertContains(page_reinitialisation, "Choisir un nouveau mot de passe")
        chemin_formulaire = page_reinitialisation.wsgi_request.path
        nouveau_mot_de_passe = "Nouveau-MotDePasse-Securise-2026"
        reponse = self.client.post(
            chemin_formulaire,
            {
                "password1": nouveau_mot_de_passe,
                "password2": nouveau_mot_de_passe,
            },
        )
        self.assertRedirects(reponse, reverse("account_reset_password_from_key_done"))
        page_terminee = self.client.get(reverse("account_reset_password_from_key_done"))
        self.assertContains(page_terminee, "Mot de passe modifié")
        self.assertTrue(
            self.client.login(
                email=self.utilisateur_candidat.email,
                password=nouveau_mot_de_passe,
            )
        )

    def test_changement_et_definition_du_mot_de_passe_sont_mis_en_page(self):
        self.client.force_login(self.utilisateur_candidat)
        page_changement = self.client.get(reverse("account_change_password"))
        self.assertEqual(page_changement.status_code, 200)
        self.assertContains(page_changement, "Changer le mot de passe")
        self.assertContains(page_changement, "/static/css/auth.css")

        utilisateur_sans_mot_de_passe = Utilisateur.objects.create_user(
            "sans-mot-de-passe@example.com", "MotDePasse-Securise-2026"
        )
        utilisateur_sans_mot_de_passe.set_unusable_password()
        utilisateur_sans_mot_de_passe.save(update_fields=["password"])
        self.client.force_login(utilisateur_sans_mot_de_passe)
        page_definition = self.client.get(reverse("account_set_password"))
        self.assertEqual(page_definition.status_code, 200)
        self.assertContains(page_definition, "Définir un mot de passe")
        self.assertContains(page_definition, "/static/css/auth.css")

    def test_formulaire_nouvelle_inscription_charge_les_choix_de_l_entite(self):
        from applications.entites.models import HoraireEntite, Option

        option = Option.objects.create(entite=self.entite_a, nom="Mathématiques")
        HoraireEntite.objects.create(entite=self.entite_a, code=HoraireEntite.Code.AM)
        self.preparer_etapes_precedentes()
        self.client.force_login(self.utilisateur_candidat)
        self.assertEqual(self.client.get("/candidatures/nouvelle/").status_code, 200)
        reponse = self.client.get(
            "/candidatures/choix-entite/", {"entite": self.entite_a.pk}
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            reponse.json()["options"], [{"id": option.pk, "nom": "Mathématiques"}]
        )
        self.assertEqual(reponse.json()["horaires"], [{"code": "AM", "nom": "AM"}])

    def test_recu_affiche_la_fiche_de_paiement_televersee(self):
        fiche = DocumentCandidat.objects.create(
            candidat=self.candidat,
            type_document=DocumentCandidat.TypeDocument.PAIEMENT,
            fichier="documents_candidats/fiche-paiement.pdf",
        )
        self.client.force_login(self.utilisateur_candidat)
        reponse = self.client.get(f"/candidatures/{self.inscription_a.pk}/recu/")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["fiche_paiement"], fiche)
        self.assertContains(reponse, "Télécharger la fiche de paiement")

    def test_administrateur_sans_entite_ne_voit_aucune_inscription(self):
        administrateur = Utilisateur.objects.create_user(
            "admin-vide@example.com", "MotDePasse-Securise-2026", is_staff=True
        )
        self.client.force_login(administrateur)
        self.assertEqual(self.client.get("/admin/").status_code, 404)
        self.client.raise_request_exception = False
        self.assertEqual(self.client.get("/gestion/inscriptions/").status_code, 403)
        self.assertFalse(Inscription.objects.pour_utilisateur(administrateur).exists())


@skipUnlessDBFeature("has_select_for_update")
class InscriptionConcurrenteTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        utilisateur = Utilisateur.objects.create_user(
            "concurrent@example.com", "MotDePasse-Securise-2026"
        )
        self.candidat = Candidat.objects.create(utilisateur=utilisateur)
        self.entite = Entite.objects.create(code="FDS", nom="Faculté des Sciences")
        for _ in range(2):
            Inscription.objects.create(
                candidat=self.candidat,
                entite=self.entite,
                annee_academique="2026-2027",
            )

    def test_deux_requetes_simultanees_ne_depassent_pas_la_limite(self):
        def creer_en_parallele():
            close_old_connections()
            try:
                candidat = Candidat.objects.get(pk=self.candidat.pk)
                Inscription.objects.create(
                    candidat=candidat,
                    entite=self.entite,
                    annee_academique="2026-2027",
                )
                return "créée"
            except ValidationError:
                return "refusée"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executeur:
            resultats = list(executeur.map(lambda _: creer_en_parallele(), range(2)))
        self.assertCountEqual(resultats, ["créée", "refusée"])
        self.assertEqual(Inscription.objects.filter(candidat=self.candidat).count(), 3)
