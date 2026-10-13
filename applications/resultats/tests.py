from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from applications.administration.models import JournalAction
from applications.candidats.models import Candidat
from applications.comptes.models import Utilisateur
from applications.candidatures.models import Inscription
from applications.entites.models import (
    AdministrateurEntite,
    Entite,
    HoraireEntite,
    Option,
    Salle,
)
from applications.resultats.models import EpreuveResultat, Resultat


class ResultatsCandidatTests(TestCase):
    def setUp(self):
        utilisateur = Utilisateur.objects.create_user(
            "resultats@example.com", "MotDePasse-Securise-2026"
        )
        self.candidat = Candidat.objects.create(utilisateur=utilisateur)
        self.entite = Entite.objects.create(code="FDS", nom="Faculté des Sciences")
        self.inscription = Inscription.objects.create(
            candidat=self.candidat,
            entite=self.entite,
            annee_academique="2026-2027",
        )
        self.client.force_login(utilisateur)

    def test_candidat_voit_ses_resultats_publies_et_le_detail_des_epreuves(self):
        resultat = Resultat.objects.create(
            inscription=self.inscription,
            admis=True,
            publie=True,
        )
        for nom, note, bareme in (
            ("Composition", "162", "300"),
            ("Culture générale", "158", "200"),
            ("Mathématiques", "40", "100"),
        ):
            EpreuveResultat.objects.create(
                resultat=resultat,
                nom=nom,
                note=Decimal(note),
                bareme=Decimal(bareme),
            )
        self.assertEqual(resultat.total_pondere, Decimal("360.00"))
        self.assertEqual(resultat.bareme_pondere, Decimal("600.00"))
        self.assertEqual(resultat.moyenne_calculee, Decimal("60.00"))
        self.assertFalse(resultat.admis_calcule)

        autre_utilisateur = Utilisateur.objects.create_user(
            "autre-resultat@example.com", "MotDePasse-Securise-2026"
        )
        autre_candidat = Candidat.objects.create(utilisateur=autre_utilisateur)
        autre_inscription = Inscription.objects.create(
            candidat=autre_candidat,
            entite=self.entite,
            annee_academique="2026-2027",
        )
        Resultat.objects.create(
            inscription=autre_inscription,
            admis=True,
            note=Decimal("99.00"),
            publie=True,
        )

        reponse = self.client.get(reverse("resultats:mes_resultats"))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(list(reponse.context["resultats"]), [resultat])
        self.assertContains(reponse, "Composition")
        self.assertContains(reponse, "Culture générale")
        self.assertContains(reponse, "Mathématiques")
        self.assertContains(reponse, "Non admis")
        self.assertContains(reponse, "360,00")
        self.assertContains(reponse, "600,00")
        self.assertContains(reponse, "60,00")
        self.assertContains(
            reponse,
            reverse("resultats:imprimer_resultat", args=[resultat.pk]),
        )
        self.assertNotContains(reponse, "99.00")

    def test_candidat_telecharge_un_ticket_pdf_pour_son_resultat_publie(self):
        resultat = Resultat.objects.create(
            inscription=self.inscription,
            note=Decimal("72.50"),
            admis=True,
            publie=True,
        )
        EpreuveResultat.objects.create(
            resultat=resultat,
            nom="Composition",
            note=Decimal("72.50"),
            bareme=Decimal("100.00"),
        )

        reponse = self.client.get(
            reverse("resultats:imprimer_resultat", args=[resultat.pk])
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse["Content-Type"], "application/pdf")
        self.assertIn("resultat-", reponse["Content-Disposition"])
        self.assertTrue(reponse.content.startswith(b"%PDF"))

    def test_ticket_pdf_est_inaccessible_pour_un_autre_candidat_ou_un_resultat_non_publie(
        self,
    ):
        resultat = Resultat.objects.create(
            inscription=self.inscription,
            publie=False,
        )

        reponse = self.client.get(
            reverse("resultats:imprimer_resultat", args=[resultat.pk])
        )

        self.assertEqual(reponse.status_code, 404)

        autre_utilisateur = Utilisateur.objects.create_user(
            "autre-ticket@example.com", "MotDePasse-Securise-2026"
        )
        autre_candidat = Candidat.objects.create(utilisateur=autre_utilisateur)
        autre_inscription = Inscription.objects.create(
            candidat=autre_candidat,
            entite=self.entite,
            annee_academique="2026-2027",
        )
        resultat_autre = Resultat.objects.create(
            inscription=autre_inscription,
            publie=True,
        )

        reponse_autre = self.client.get(
            reverse("resultats:imprimer_resultat", args=[resultat_autre.pk])
        )

        self.assertEqual(reponse_autre.status_code, 404)

    def test_resultat_non_publie_reste_invisible(self):
        Resultat.objects.create(inscription=self.inscription, admis=True, publie=False)

        reponse = self.client.get(reverse("resultats:mes_resultats"))

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(reponse.context["resultats"].exists())
        self.assertContains(reponse, "Aucun résultat n'a été publié.")

    def test_admission_est_automatique_a_soixante_cinq_sur_cent(self):
        resultat = Resultat.objects.create(
            inscription=self.inscription,
            note=Decimal("64.99"),
            publie=True,
        )
        self.assertFalse(resultat.admis_calcule)

        resultat.note = Decimal("65.00")

        self.assertTrue(resultat.admis_calcule)


class ResultatAdminTests(TestCase):
    def setUp(self):
        utilisateur = Utilisateur.objects.create_user(
            "admin-resultats-candidat@example.com", "MotDePasse-Securise-2026"
        )
        candidat = Candidat.objects.create(utilisateur=utilisateur)
        entite = Entite.objects.create(code="FDS", nom="Faculté des Sciences")
        self.inscription = Inscription.objects.create(
            candidat=candidat,
            entite=entite,
            annee_academique="2026-2027",
        )
        superutilisateur = Utilisateur.objects.create_superuser(
            "super-resultats@example.com", "MotDePasse-Securise-2026"
        )
        self.client.force_login(superutilisateur)

    def test_matieres_filtrees_par_inscription_et_option(self):
        option = Option.objects.create(
            entite=self.inscription.entite, nom="Génie Civil"
        )
        self.inscription.option = option
        self.inscription.save()
        url = reverse("admin:resultats_resultat_matieres")

        reponse = self.client.get(url, {"inscription": self.inscription.pk})

        self.assertEqual(reponse.status_code, 200)
        groupes = reponse.json()["groupes"]
        self.assertEqual(len(groupes), 1)
        self.assertEqual(groupes[0]["nom"], "FDS — Génie Civil")
        self.assertIn("Mathématiques", groupes[0]["matieres"])
        self.assertNotIn("Administration Publique", groupes[0]["matieres"])

    def test_inscription_edj_n_a_pas_de_matieres_absentes_du_csv(self):
        entite = Entite.objects.create(code="EDJ", nom="École de Droit de Jacmel")
        inscription = Inscription.objects.create(
            candidat=self.inscription.candidat,
            entite=entite,
            annee_academique="2026-2027",
        )
        url = reverse("admin:resultats_resultat_matieres")

        reponse = self.client.get(url, {"inscription": inscription.pk})

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()["groupes"], [])

    def test_superuser_peut_creer_un_resultat_avec_ses_epreuves(self):
        url = reverse("admin:resultats_resultat_add")
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'class="form-control"', html=False)
        self.assertContains(page, "Épreuves de résultat")
        self.assertNotContains(page, 'name="admis"', html=False)
        self.assertContains(page, 'name="epreuves-0-nom"', html=False)
        self.assertNotContains(page, '<select name="epreuves-0-nom"', html=False)
        self.assertContains(
            page,
            f'data-url-matieres="{reverse("admin:resultats_resultat_matieres")}"',
            html=False,
        )
        self.assertContains(page, "admin-resultats-matieres.js")

        reponse = self.client.post(
            url,
            {
                "inscription": self.inscription.pk,
                "note": "65.00",
                "publie": "on",
                "epreuves-TOTAL_FORMS": "1",
                "epreuves-INITIAL_FORMS": "0",
                "epreuves-MIN_NUM_FORMS": "0",
                "epreuves-MAX_NUM_FORMS": "1000",
                "epreuves-0-nom": "Matière ajoutée manuellement",
                "epreuves-0-note": "195.00",
                "epreuves-0-bareme": "300.00",
                "epreuves-0-coefficient": "1.00",
                "epreuves-0-ordre": "1",
            },
        )

        self.assertEqual(reponse.status_code, 302)
        resultat = Resultat.objects.get(inscription=self.inscription)
        self.assertTrue(resultat.publie)
        self.assertIsNotNone(resultat.date_publication)
        self.assertEqual(resultat.note, Decimal("65.00"))
        self.assertTrue(resultat.admis)
        self.assertEqual(resultat.epreuves.get().nom, "Matière ajoutée manuellement")


class AdministrationLocaleTests(TestCase):
    def setUp(self):
        self.entite_locale = Entite.objects.create(
            code="FDS", nom="Faculté des Sciences"
        )
        self.entite_autre = Entite.objects.create(code="FMP", nom="Faculté de Médecine")
        self.candidat_local = Candidat.objects.create(
            utilisateur=Utilisateur.objects.create_user(
                "candidat-local@example.com", "MotDePasse-Securise-2026"
            )
        )
        self.candidat_autre = Candidat.objects.create(
            utilisateur=Utilisateur.objects.create_user(
                "candidat-autre@example.com", "MotDePasse-Securise-2026"
            )
        )
        self.inscription_locale = Inscription.objects.create(
            candidat=self.candidat_local,
            entite=self.entite_locale,
            annee_academique="2026-2027",
        )
        self.inscription_autre = Inscription.objects.create(
            candidat=self.candidat_autre,
            entite=self.entite_autre,
            annee_academique="2026-2027",
        )
        self.resultat_local = Resultat.objects.create(
            inscription=self.inscription_locale, publie=False
        )
        self.resultat_autre = Resultat.objects.create(
            inscription=self.inscription_autre, publie=True
        )
        self.admin_local = Utilisateur.objects.create_user(
            "admin-local@example.com", "MotDePasse-Securise-2026", is_staff=True
        )
        AdministrateurEntite.objects.create(
            utilisateur=self.admin_local, entite=self.entite_locale
        )
        self.client.force_login(self.admin_local)

    def test_admin_local_voit_uniquement_ses_dossiers_et_peut_gerer_le_resultat(self):
        page = self.client.get(reverse("resultats:mes_resultats"))

        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context["vue_administration"])
        self.assertEqual(
            [inscription.pk for inscription in page.context["inscriptions"]],
            [self.inscription_locale.pk],
        )
        self.assertContains(page, "Modifier le dossier complet")
        self.assertContains(
            page,
            reverse("administration:gerer_resultat", args=[self.inscription_locale.pk]),
        )
        self.assertRedirects(
            self.client.get(
                reverse(
                    "admin:resultats_resultat_change", args=[self.resultat_local.pk]
                )
            ),
            "/gestion/inscriptions/",
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "administration:gerer_resultat", args=[self.inscription_autre.pk]
                )
            ).status_code,
            404,
        )

    def test_admin_local_peut_modifier_le_dossier_complet_de_son_candidat(self):
        url = reverse(
            "administration:modifier_candidat", args=[self.inscription_locale.pk]
        )
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)

        reponse = self.client.post(
            url,
            {
                "prenom": "Marie",
                "nom": "Jean",
                "nationalite": "Haïtienne",
                "telephone": "50912345678",
                "date_naissance": "1990-01-15",
                "lieu_naissance": "Port-au-Prince",
                "sexe": Candidat.Sexe.FEMININ,
                "nom_parent_responsable": "",
                "nif": "000-000-000-0",
                "ninu": "",
                "adresse": "Rue de la Paix",
                "departement_geographique": Candidat.Departement.OUEST,
                "ville": "Port-au-Prince",
                "etablissement_scolaire": "Lycée UEH",
                "annee_obtention": "2024",
                "ecoles-TOTAL_FORMS": "1",
                "ecoles-INITIAL_FORMS": "0",
                "ecoles-MIN_NUM_FORMS": "0",
                "ecoles-MAX_NUM_FORMS": "1000",
                "parcours-TOTAL_FORMS": "1",
                "parcours-INITIAL_FORMS": "0",
                "parcours-MIN_NUM_FORMS": "0",
                "parcours-MAX_NUM_FORMS": "1000",
                "documents-TOTAL_FORMS": "1",
                "documents-INITIAL_FORMS": "0",
                "documents-MIN_NUM_FORMS": "0",
                "documents-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertEqual(reponse.status_code, 302)
        self.candidat_local.refresh_from_db()
        self.candidat_local.utilisateur.refresh_from_db()
        self.assertEqual(self.candidat_local.telephone, "50912345678")
        self.assertEqual(self.candidat_local.utilisateur.get_full_name(), "Marie Jean")
        entree_audit = JournalAction.objects.get(
            inscription=self.inscription_locale,
            action=JournalAction.Action.MODIFICATION_DOSSIER,
        )
        self.assertIn("telephone", entree_audit.details["champs_modifies"])
        self.assertNotIn("50912345678", str(entree_audit.details))

        url_autre = reverse(
            "administration:modifier_candidat", args=[self.inscription_autre.pk]
        )
        self.assertEqual(self.client.get(url_autre).status_code, 404)

    def test_popup_salle_preselectionne_et_limite_a_l_entite_locale(self):
        affectation = self.client.get(
            reverse(
                "administration:affecter_salle",
                args=[self.inscription_locale.pk],
            )
        )
        self.assertEqual(affectation.status_code, 200)
        self.assertContains(
            affectation,
            f'href="{reverse("administration:liste_salles")}"',
            html=False,
        )
        gestion_salles = self.client.get(reverse("administration:liste_salles"))
        self.assertEqual(gestion_salles.status_code, 200)
        self.assertContains(gestion_salles, 'class="form-control"', html=False)
        self.assertTrue(
            gestion_salles.context["formulaire"].fields["entite"].widget.is_hidden
        )
        self.assertEqual(
            list(gestion_salles.context["formulaire"].fields["entite"].queryset),
            [self.entite_locale],
        )

    def test_admin_local_cree_une_salle_une_option_et_un_horaire_dans_son_entite(self):
        reponse_salle = self.client.post(
            reverse("administration:liste_salles"),
            {
                "entite": self.entite_locale.pk,
                "nom": "Salle Démo",
                "capacite": "30",
            },
        )
        self.assertRedirects(reponse_salle, reverse("administration:liste_salles"))
        self.assertTrue(
            Salle.objects.filter(entite=self.entite_locale, nom="Salle Démo").exists()
        )

        reponse_option = self.client.post(
            reverse("administration:liste_options"),
            {"entite": self.entite_locale.pk, "nom": "Option Démo", "active": "on"},
        )
        self.assertRedirects(reponse_option, reverse("administration:liste_options"))
        self.assertTrue(
            Option.objects.filter(entite=self.entite_locale, nom="Option Démo").exists()
        )

        reponse_horaire = self.client.post(
            reverse("administration:liste_horaires"),
            {
                "entite": self.entite_locale.pk,
                "code": HoraireEntite.Code.AM,
                "actif": "on",
            },
        )
        self.assertRedirects(reponse_horaire, reverse("administration:liste_horaires"))
        self.assertTrue(
            HoraireEntite.objects.filter(
                entite=self.entite_locale, code=HoraireEntite.Code.AM
            ).exists()
        )

        refus = self.client.post(
            reverse("administration:liste_salles"),
            {
                "entite": self.entite_autre.pk,
                "nom": "Salle hors périmètre",
                "capacite": "20",
            },
        )
        self.assertEqual(refus.status_code, 400)
        self.assertFalse(Salle.objects.filter(nom="Salle hors périmètre").exists())
        self.assertTrue(
            JournalAction.objects.filter(
                entite=self.entite_locale,
                utilisateur=self.admin_local,
                action=JournalAction.Action.CREATION_SALLE,
            ).exists()
        )

    def test_admin_local_saisit_un_resultat_sans_ouvrir_django_admin(self):
        url = reverse(
            "administration:gerer_resultat", args=[self.inscription_locale.pk]
        )
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Gérer le résultat")
        self.assertContains(page, 'class="form-control"', html=False)

        reponse = self.client.post(
            url,
            {
                "publie": "on",
                "epreuves-TOTAL_FORMS": "1",
                "epreuves-INITIAL_FORMS": "0",
                "epreuves-MIN_NUM_FORMS": "0",
                "epreuves-MAX_NUM_FORMS": "1000",
                "epreuves-0-nom": "Mathématiques",
                "epreuves-0-note": "195.00",
                "epreuves-0-bareme": "300.00",
                "epreuves-0-coefficient": "1.00",
                "epreuves-0-ordre": "1",
            },
        )
        self.assertRedirects(reponse, reverse("resultats:mes_resultats"))
        resultat = Resultat.objects.get(inscription=self.inscription_locale)
        self.assertTrue(resultat.publie)
        self.assertIsNotNone(resultat.date_publication)
        self.assertEqual(resultat.note, Decimal("65.00"))
        self.assertTrue(resultat.admis)
        self.assertTrue(
            JournalAction.objects.filter(
                inscription=self.inscription_locale,
                utilisateur=self.admin_local,
                action=JournalAction.Action.MODIF_RESULTAT,
            ).exists()
        )
