import re
from datetime import date
from urllib.parse import urlsplit

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from applications.comptes.models import (
    ProfilEtudiant,
    SiteConfiguration,
    Utilisateur,
)
from applications.inscriptions.models import InscriptionPedagogique
from applications.rapports.models import DossierEtudes
from applications.referentiels.models import Cours, Entite, PeriodeAcademique, Programme


class ComptesUnifiesTests(TestCase):
    def test_synchronise_les_noms_gp7_et_admission(self):
        utilisateur = Utilisateur.objects.create_user(
            "noms@example.test",
            "MotDePasse-Securise-2026",
        )

        utilisateur.prenom = "Marie"
        utilisateur.nom = "Jean"
        utilisateur.save(update_fields=("prenom", "nom"))
        utilisateur.refresh_from_db()

        self.assertEqual(
            (utilisateur.first_name, utilisateur.last_name),
            ("Marie", "Jean"),
        )
        self.assertTrue(Utilisateur.objects.filter(prenom="Marie", nom="Jean").exists())

        utilisateur.first_name = "Nadia"
        utilisateur.last_name = "Baptiste"
        utilisateur.save(update_fields=("first_name", "last_name"))
        utilisateur.refresh_from_db()

        self.assertEqual((utilisateur.prenom, utilisateur.nom), ("Nadia", "Baptiste"))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RecuperationMotDePasseTests(TestCase):
    def setUp(self):
        self.mot_de_passe_initial = "Ancien-mot-de-passe-2026!"
        self.utilisateur = Utilisateur.objects.create_user(
            username="utilisateur-recup",
            email="utilisateur-recup@example.test",
            password=self.mot_de_passe_initial,
        )

    def test_lien_oublie_est_present_et_les_champs_password_ont_un_controle_oeil(self):
        reponse = self.client.get(reverse("comptes:connexion"))

        self.assertContains(reponse, reverse("comptes:password_reset"))
        self.assertContains(reponse, "Afficher le mot de passe")
        self.assertContains(reponse, 'input[type="password"]')
        self.assertNotContains(reponse, 'class="barre-laterale"')

    def test_parcours_complet_reinitialise_le_mot_de_passe_et_connecte_le_compte(self):
        demande = self.client.post(
            reverse("comptes:password_reset"),
            {"email": self.utilisateur.email},
        )

        self.assertRedirects(demande, reverse("comptes:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.utilisateur.email, mail.outbox[0].to)

        lien = re.search(r"https?://[^/\s]+(?P<path>/\S+)", mail.outbox[0].body)
        self.assertIsNotNone(lien)
        chemin = urlsplit(lien.group(0)).path
        formulaire = self.client.get(chemin, follow=True)
        self.assertEqual(formulaire.status_code, 200)
        self.assertContains(formulaire, 'name="new_password1"')
        self.assertContains(formulaire, "Afficher le mot de passe")
        chemin_confirmation = formulaire.wsgi_request.path

        nouveau_mot_de_passe = "Nouveau-mot-de-passe-securise-2026!"
        confirmation = self.client.post(
            chemin_confirmation,
            {
                "new_password1": nouveau_mot_de_passe,
                "new_password2": nouveau_mot_de_passe,
            },
        )

        self.assertRedirects(
            confirmation,
            reverse("comptes:password_reset_complete"),
        )
        self.utilisateur.refresh_from_db()
        self.assertTrue(self.utilisateur.check_password(nouveau_mot_de_passe))
        self.assertFalse(self.utilisateur.check_password(self.mot_de_passe_initial))
        self.assertTrue(
            self.client.login(
                username=self.utilisateur.username,
                password=nouveau_mot_de_passe,
            )
        )

    def test_email_inconnu_ne_revele_pas_si_un_compte_existe(self):
        reponse = self.client.post(
            reverse("comptes:password_reset"),
            {"email": "inconnu@example.test"},
        )

        self.assertRedirects(reponse, reverse("comptes:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(
            self.client.get(reverse("comptes:password_reset_done")),
            "Si un compte actif utilise cette adresse",
            status_code=200,
        )


class PublicLandingAndEmailLoginTests(TestCase):
    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="prenom.nom",
            email="prenom.nom@example.test",
            password="mot-de-passe-123",
            first_name="Prenom",
            last_name="Nom",
            role=Utilisateur.Role.ETUDIANT,
        )
        self.config = SiteConfiguration.objects.create(
            nom_site="Institut Lumiere",
            slogan="Former les talents du demain",
            telephone="+509 1234 5678",
            email_contact="contact@institut-lumiere.test",
            adresse="Rue de l'Education, Port-au-Prince",
            texte_pied_page="Une mention definie dans la configuration.",
        )

    def test_landing_publique_existe_et_ne_redirige_pas_vers_connexion(self):
        reponse = self.client.get(reverse("comptes:landing"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Institut Lumiere")
        self.assertContains(reponse, "Former les talents du demain")
        self.assertContains(reponse, reverse("comptes:connexion"))
        self.assertContains(reponse, reverse("contact:contact"))
        self.assertContains(reponse, 'href="/admission/"')
        self.assertContains(reponse, "public-footer-logo")
        self.assertNotContains(reponse, 'class="barre-laterale"')

    def test_landing_affiche_des_indicateurs_calcules_depuis_la_base(self):
        entite = Entite.objects.create(
            code="landing-famv",
            nom="Faculte de demonstration",
            regime=Entite.Regime.COHORTE,
        )
        programme = Programme.objects.create(
            entite=entite,
            code="programme-landing",
            nom="Programme public",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        cours = Cours.objects.create(
            programme=programme,
            code="PUB101",
            nom="Cours public",
        )
        periode = PeriodeAcademique.objects.create(
            entite=entite,
            code="periode-landing",
            nom="Session publique",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
            date_debut=date(2026, 10, 1),
            date_fin=date(2027, 2, 1),
        )
        self.utilisateur.entite = entite
        self.utilisateur.save(update_fields=("entite",))
        Utilisateur.objects.create_user(
            username="professeur-landing",
            email="professeur-landing@example.test",
            password="mot-de-passe-test",
            role=Utilisateur.Role.PROFESSEUR,
            entite=entite,
        )
        InscriptionPedagogique.objects.create(
            etudiant=self.utilisateur,
            programme=programme,
            periode=periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
        )

        reponse = self.client.get(reverse("comptes:landing"))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            reponse.context["statistiques"],
            {
                "entites": 1,
                "programmes": 1,
                "etudiants": 1,
                "professeurs": 1,
                "cours": 1,
            },
        )
        self.assertContains(reponse, programme.nom)
        self.assertContains(reponse, periode.nom)
        self.assertContains(reponse, "Cours actifs")

    def test_connexion_par_email_est_autorisee(self):
        reponse = self.client.post(
            reverse("comptes:connexion"),
            {"username": self.utilisateur.email, "password": "mot-de-passe-123"},
            follow=True,
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.context["user"].is_authenticated)
        self.assertRedirects(
            reponse, reverse("comptes:tableau_de_bord"), fetch_redirect_response=False
        )

    def test_tableau_de_bord_affiche_l_identite_sans_avatar_flottant(self):
        self.client.force_login(self.utilisateur)

        reponse = self.client.get(reverse("comptes:tableau_de_bord"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'class="profil-utilisateur"')
        self.assertContains(reponse, 'href="/mon-profil/"')
        self.assertContains(reponse, 'action="/deconnexion/"')
        self.assertNotContains(reponse, 'class="menu-utilisateur-wrapper"')
        self.assertNotContains(reponse, 'class="menu-utilisateur-bouton"')
        self.assertContains(reponse, 'id="confirmation-deconnexion"')
        self.assertContains(reponse, 'aria-labelledby="confirmation-deconnexion-titre"')
        self.assertContains(
            reponse, f'href="{reverse("comptes:landing")}"'
        )
        self.assertContains(reponse, "Page publique")

    def test_deconnexion_exige_un_post_et_le_post_termine_la_session(self):
        self.client.force_login(self.utilisateur)

        reponse_get = self.client.get(reverse("comptes:deconnexion"))
        self.assertEqual(reponse_get.status_code, 405)
        self.assertEqual(
            self.client.get(reverse("comptes:tableau_de_bord")).status_code,
            200,
        )

        reponse_post = self.client.post(reverse("comptes:deconnexion"))
        self.assertRedirects(
            reponse_post,
            reverse("comptes:landing"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get(reverse("comptes:tableau_de_bord")),
            f"{reverse('comptes:connexion')}?next={reverse('comptes:tableau_de_bord')}",
            fetch_redirect_response=False,
        )

    def test_navigation_mobile_garde_les_acces_rapides_et_le_menu_plus(self):
        self.client.force_login(self.utilisateur)

        reponse = self.client.get(reverse("comptes:tableau_de_bord"))
        contenu = reponse.content.decode()

        navigation_mobile = contenu.split('<nav class="navigation-mobile"', 1)[1].split(
            "</nav>", 1
        )[0]
        panneau_plus = contenu.split('id="mobile-plus-panel"', 1)[1].split(
            "</aside>", 1
        )[0]
        self.assertEqual(navigation_mobile.count('class="navigation-mobile-lien'), 5)
        self.assertContains(reponse, 'aria-label="Navigation mobile"')
        self.assertContains(reponse, 'aria-controls="mobile-plus-panel"')
        self.assertContains(reponse, reverse("comptes:profil"))
        self.assertNotContains(reponse, 'class="mobile-plus-profil"')
        self.assertContains(reponse, reverse("notes:resultats_etudiant"))
        self.assertContains(reponse, reverse("rapports:actes_etudiant"))
        for lien_epingle in (
            reverse("comptes:tableau_de_bord"),
            reverse("inscriptions:paiement_etudiant"),
            reverse("inscriptions:inscription_etudiant"),
            reverse("comptes:profil"),
        ):
            self.assertNotIn(f'href="{lien_epingle}"', panneau_plus)

    def test_marque_du_panneau_utilise_la_configuration_du_site(self):
        self.client.force_login(self.utilisateur)

        reponse = self.client.get(reverse("comptes:tableau_de_bord"))

        self.assertContains(reponse, 'class="marque-libelle"')
        self.assertContains(reponse, self.config.nom_site)
        self.assertNotContains(reponse, ">GP7 <small>REGISTRARIAT</small>")

    @override_settings(DEBUG=True)
    def test_logo_configure_est_visible_et_enregistre(self):
        contenu_logo = b"contenu-logo-test"
        self.config.logo.save(
            "logo-test.png",
            SimpleUploadedFile("logo-test.png", contenu_logo, content_type="image/png"),
            save=True,
        )

        try:
            page = self.client.get(reverse("comptes:landing"))
            self.assertContains(page, self.config.logo.url)
            self.assertTrue(self.config.logo.storage.exists(self.config.logo.name))
        finally:
            self.config.logo.delete(save=False)

    def test_page_profil_est_disponible_et_permet_le_chargement_photo(self):
        self.client.force_login(self.utilisateur)

        reponse = self.client.get(reverse("comptes:profil"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'enctype="multipart/form-data"')
        self.assertContains(reponse, 'name="photo_profil"')

    def test_etudiant_voit_son_code_et_ses_dossiers_uniquement(self):
        entite = Entite.objects.create(
            code="profil-famv",
            nom="Faculte de profil",
            regime=Entite.Regime.COHORTE,
        )
        programme = Programme.objects.create(
            entite=entite,
            code="agronomie-profil",
            nom="Agronomie",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        programme_prive = Programme.objects.create(
            entite=entite,
            code="secret-profil",
            nom="Programme d'un autre etudiant",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        personnel = Utilisateur.objects.create_user(
            username="registrariat-profil",
            email="registrariat-profil@example.test",
            password="mot-de-passe-de-test",
            role=Utilisateur.Role.PERSONNEL,
            entite=entite,
        )
        self.utilisateur.entite = entite
        self.utilisateur.save(update_fields=("entite",))
        ProfilEtudiant.objects.create(
            utilisateur=self.utilisateur,
            code_etudiant="FAMV-2026-0042",
        )
        DossierEtudes.objects.create(
            etudiant=self.utilisateur,
            programme=programme,
            statut=DossierEtudes.Statut.EN_COURS,
            date_ouverture=date(2026, 9, 1),
            cree_par=personnel,
        )
        autre_etudiant = Utilisateur.objects.create_user(
            username="autre-etudiant-profil",
            email="autre-etudiant-profil@example.test",
            password="mot-de-passe-de-test",
            role=Utilisateur.Role.ETUDIANT,
            entite=entite,
        )
        DossierEtudes.objects.create(
            etudiant=autre_etudiant,
            programme=programme_prive,
            statut=DossierEtudes.Statut.EN_COURS,
            date_ouverture=date(2026, 9, 1),
            cree_par=personnel,
        )
        self.client.force_login(self.utilisateur)

        reponse = self.client.get(reverse("comptes:profil"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "FAMV-2026-0042")
        self.assertContains(reponse, "Mes dossiers d'etudes")
        self.assertContains(reponse, "Agronomie")
        self.assertContains(reponse, "Etudes en cours")
        self.assertNotContains(reponse, "Programme d'un autre etudiant")

    def test_page_profil_enregistre_la_photo_envoyee(self):
        self.client.force_login(self.utilisateur)
        photo = SimpleUploadedFile(
            "profil.png", b"contenu-test", content_type="image/png"
        )

        try:
            reponse = self.client.post(
                reverse("comptes:profil"), {"photo_profil": photo}
            )

            self.assertRedirects(reponse, reverse("comptes:profil"))
            self.utilisateur.refresh_from_db()
            self.assertTrue(self.utilisateur.photo_profil)
        finally:
            self.utilisateur.photo_profil.delete(save=False)

    def test_configuration_site_est_reservee_aux_administrateurs(self):
        self.client.force_login(self.utilisateur)

        reponse = self.client.get(reverse("comptes:configuration_site"))

        self.assertEqual(reponse.status_code, 403)

    def test_administrateur_configure_le_site_sans_interface_admin(self):
        self.utilisateur.role = Utilisateur.Role.ADMINISTRATEUR
        self.utilisateur.save(update_fields=["role"])
        self.client.force_login(self.utilisateur)

        page = self.client.get(reverse("comptes:configuration_site"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, reverse("comptes:configuration_site"))
        self.assertContains(page, 'id="apercu-logo-site"')
        self.assertContains(page, "URL.createObjectURL(fichier)")
        self.assertNotContains(page, "/admin/")

        reponse = self.client.post(
            reverse("comptes:configuration_site"),
            {
                "nom_site": "Institut Horizon",
                "slogan": "Apprendre et avancer",
                "telephone": "+509 5555 0101",
                "email_contact": "contact@horizon.test",
                "adresse": "Port-au-Prince",
                "texte_pied_page": "Institut Horizon 2026",
            },
        )

        self.assertRedirects(reponse, reverse("comptes:configuration_site"))
        self.config.refresh_from_db()
        self.assertEqual(self.config.nom_site, "Institut Horizon")
        self.assertEqual(self.config.slogan, "Apprendre et avancer")
        self.assertEqual(self.config.email_contact, "contact@horizon.test")

    def test_formulaire_de_connexion_indique_email_ou_nom_utilisateur(self):
        reponse = self.client.get(reverse("comptes:connexion"))
        self.assertContains(reponse, "Nom d'utilisateur ou adresse e-mail")
        self.assertContains(
            reponse,
            "Connectez-vous avec votre adresse e-mail ou votre nom d'utilisateur.",
        )

    def test_un_utilisateur_connecte_peut_acceder_a_la_page_publique(self):
        self.client.force_login(self.utilisateur)
        reponse = self.client.get(reverse("comptes:landing"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Institut Lumiere")
        self.assertContains(reponse, reverse("comptes:tableau_de_bord"))

    def test_landing_publique_ne_affiche_pas_la_barre_laterale_quand_utilisateur_connecte(
        self,
    ):
        self.client.force_login(self.utilisateur)
        reponse = self.client.get(reverse("comptes:landing"))

        self.assertEqual(reponse.status_code, 200)
        self.assertNotContains(reponse, 'class="barre-laterale"')

    def test_la_config_du_site_est_affichee_en_public(self):
        reponse = self.client.get(reverse("comptes:landing"))
        self.assertContains(reponse, self.config.nom_site)
        self.assertContains(reponse, self.config.telephone)
        self.assertContains(reponse, self.config.email_contact)
        self.assertContains(reponse, "Port-au-Prince")
        self.assertContains(reponse, self.config.texte_pied_page)
