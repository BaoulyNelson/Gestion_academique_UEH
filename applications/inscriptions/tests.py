from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from applications.audit.models import JournalAction
from applications.comptes.models import ProfilEtudiant, Utilisateur
from applications.inscriptions.models import (
    InscriptionPedagogique,
    PaiementScolarite,
    SelectionCours,
    TarifScolarite,
)
from applications.inscriptions.services.paiements import (
    frais_scolarite_acquittes,
    montant_scolarite_confirme,
)
from applications.notes.models import Evaluation
from applications.referentiels.models import (
    AffectationCours,
    Cours,
    Entite,
    PeriodeAcademique,
    Programme,
)


class ListeCoursProfesseurTests(TestCase):
    def setUp(self):
        self.entite = Entite.objects.create(
            code="famv",
            nom="Faculte d'agronomie",
            regime=Entite.Regime.COHORTE,
        )
        self.programme = Programme.objects.create(
            entite=self.entite,
            code="agronomie",
            nom="Agronomie",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        self.periode = PeriodeAcademique.objects.create(
            entite=self.entite,
            code="2026-s1",
            nom="Premiere session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
        )
        self.cours_professeur = Cours.objects.create(
            programme=self.programme, code="AGR101", nom="Agronomie generale"
        )
        self.cours_autre_professeur = Cours.objects.create(
            programme=self.programme, code="BIO101", nom="Biologie generale"
        )
        self.professeur = self.creer_utilisateur(
            "professeur", Utilisateur.Role.PROFESSEUR
        )
        self.autre_professeur = self.creer_utilisateur(
            "autre-professeur", Utilisateur.Role.PROFESSEUR
        )
        AffectationCours.objects.create(
            professeur=self.professeur,
            cours=self.cours_professeur,
            periode=self.periode,
        )
        AffectationCours.objects.create(
            professeur=self.autre_professeur,
            cours=self.cours_autre_professeur,
            periode=self.periode,
        )

    def creer_utilisateur(self, nom, role):
        return Utilisateur.objects.create_user(
            username=nom,
            email=f"{nom}@example.test",
            password="mot-de-passe-de-test",
            role=role,
            entite=self.entite,
        )

    def creer_inscription(self, nom, cours, statut):
        etudiant = self.creer_utilisateur(nom, Utilisateur.Role.ETUDIANT)
        inscription = InscriptionPedagogique.objects.create(
            etudiant=etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=statut,
        )
        SelectionCours.objects.create(inscription=inscription, cours=cours)
        return etudiant

    def test_professeur_ne_voit_que_ses_inscriptions_validees(self):
        etudiant_visible = self.creer_inscription(
            "etudiant-visible",
            self.cours_professeur,
            InscriptionPedagogique.Statut.VALIDEE,
        )
        etudiant_autre_cours = self.creer_inscription(
            "etudiant-autre-cours",
            self.cours_autre_professeur,
            InscriptionPedagogique.Statut.VALIDEE,
        )
        etudiant_en_attente = self.creer_inscription(
            "etudiant-en-attente",
            self.cours_professeur,
            InscriptionPedagogique.Statut.EN_ATTENTE,
        )
        self.client.force_login(self.professeur)

        reponse = self.client.get(reverse("inscriptions:cours_professeur"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, etudiant_visible.username)
        self.assertNotContains(reponse, etudiant_autre_cours.username)
        self.assertNotContains(reponse, etudiant_en_attente.username)

    def test_professeur_peut_filtrer_et_imprimer_ses_etudiants_uniquement(self):
        etudiant_visible = self.creer_inscription(
            "etudiant-imprimable",
            self.cours_professeur,
            InscriptionPedagogique.Statut.VALIDEE,
        )
        etudiant_autre_cours = self.creer_inscription(
            "etudiant-imprimable-autre-cours",
            self.cours_autre_professeur,
            InscriptionPedagogique.Statut.VALIDEE,
        )
        etudiant_en_attente = self.creer_inscription(
            "etudiant-imprimable-en-attente",
            self.cours_professeur,
            InscriptionPedagogique.Statut.EN_ATTENTE,
        )
        self.client.force_login(self.professeur)

        reponse = self.client.get(reverse("inscriptions:etudiants_professeur"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, etudiant_visible.username)
        self.assertNotContains(reponse, etudiant_autre_cours.username)
        self.assertNotContains(reponse, etudiant_en_attente.username)
        self.assertContains(reponse, "window.print()")
        self.assertContains(reponse, "@media print")

        filtre_hors_affectation = self.client.get(
            reverse("inscriptions:etudiants_professeur"),
            {"cours": self.cours_autre_professeur.pk},
        )
        self.assertNotContains(filtre_hors_affectation, etudiant_autre_cours.username)

    def test_eleve_ne_voit_que_les_professeurs_de_ses_cours_valides(self):
        eleve = self.creer_inscription(
            "eleve-professeurs",
            self.cours_professeur,
            InscriptionPedagogique.Statut.VALIDEE,
        )
        self.creer_inscription(
            "eleve-autre-cours-professeurs",
            self.cours_autre_professeur,
            InscriptionPedagogique.Statut.VALIDEE,
        )
        self.creer_inscription(
            "eleve-inscription-attente-professeurs",
            self.cours_professeur,
            InscriptionPedagogique.Statut.EN_ATTENTE,
        )
        autre_periode = PeriodeAcademique.objects.create(
            entite=self.entite,
            code="2026-s2",
            nom="Deuxieme session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
        )
        professeur_autre_periode = self.creer_utilisateur(
            "professeur-autre-periode", Utilisateur.Role.PROFESSEUR
        )
        AffectationCours.objects.create(
            professeur=professeur_autre_periode,
            cours=self.cours_professeur,
            periode=autre_periode,
        )
        self.client.force_login(eleve)

        reponse = self.client.get(reverse("inscriptions:professeurs_etudiant"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.professeur.username)
        self.assertContains(reponse, self.cours_professeur.code)
        self.assertNotContains(reponse, self.autre_professeur.username)
        self.assertNotContains(reponse, professeur_autre_periode.username)

    def test_eleve_voit_uniquement_ses_cours_selectionnes_valides(self):
        etudiant = self.creer_inscription(
            "eleve-mes-cours",
            self.cours_professeur,
            InscriptionPedagogique.Statut.VALIDEE,
        )
        etudiant.inscriptions_pedagogiques.update(conditions_passage_verifiees=True)
        self.creer_inscription(
            "autre-eleve-mes-cours",
            self.cours_autre_professeur,
            InscriptionPedagogique.Statut.VALIDEE,
        )
        self.creer_inscription(
            "demande-en-attente-mes-cours",
            self.cours_professeur,
            InscriptionPedagogique.Statut.EN_ATTENTE,
        )
        self.client.force_login(etudiant)

        reponse = self.client.get(reverse("inscriptions:cours_etudiant"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.cours_professeur.code)
        self.assertContains(reponse, self.professeur.username)
        self.assertNotContains(reponse, self.cours_autre_professeur.code)
        self.assertNotContains(reponse, "demande-en-attente-mes-cours")

    def test_professeur_ne_peut_pas_ouvrir_les_cours_personnels_etudiants(self):
        self.client.force_login(self.professeur)

        reponse = self.client.get(reverse("inscriptions:cours_etudiant"))

        self.assertEqual(reponse.status_code, 403)

    def test_professeur_ne_peut_pas_ouvrir_la_liste_de_professeurs_etudiants(self):
        self.client.force_login(self.professeur)

        reponse = self.client.get(reverse("inscriptions:professeurs_etudiant"))

        self.assertEqual(reponse.status_code, 403)

    def test_etudiant_ne_peut_pas_ouvrir_la_liste_professeur(self):
        etudiant = self.creer_utilisateur("etudiant", Utilisateur.Role.ETUDIANT)
        self.client.force_login(etudiant)

        reponse = self.client.get(reverse("inscriptions:cours_professeur"))
        reponse_etudiants = self.client.get(
            reverse("inscriptions:etudiants_professeur")
        )

        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(reponse_etudiants.status_code, 403)

    def test_tableau_professeur_affiche_ses_indicateurs_affectes(self):
        etudiant = self.creer_inscription(
            "etudiant-indicateurs-prof",
            self.cours_professeur,
            InscriptionPedagogique.Statut.VALIDEE,
        )
        self.creer_inscription(
            "etudiant-indicateurs-autre-prof",
            self.cours_autre_professeur,
            InscriptionPedagogique.Statut.VALIDEE,
        )
        for libelle, publiee in (("Devoir", False), ("Examen", True)):
            Evaluation.objects.create(
                etudiant=etudiant,
                cours=self.cours_professeur,
                periode=self.periode,
                libelle=libelle,
                note=75,
                coefficient=1,
                est_publiee=publiee,
                saisie_par=self.professeur,
            )
        self.client.force_login(self.professeur)

        reponse = self.client.get(reverse("comptes:tableau_de_bord"))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["nombre_cours_professeur"], 1)
        self.assertEqual(reponse.context["nombre_etudiants"], 1)
        self.assertEqual(reponse.context["nombre_notes_a_valider"], 1)
        self.assertEqual(reponse.context["nombre_notes_publiees"], 1)
        self.assertContains(reponse, "Cours affectes")
        self.assertContains(reponse, reverse("inscriptions:etudiants_professeur"))

    def test_affectation_refuse_un_compte_sans_role_professeur(self):
        etudiant = self.creer_utilisateur("non-professeur", Utilisateur.Role.ETUDIANT)
        affectation = AffectationCours(
            professeur=etudiant,
            cours=self.cours_professeur,
            periode=self.periode,
        )

        with self.assertRaisesMessage(ValidationError, "role professeur"):
            affectation.full_clean()


class NavigationPersistanteTests(TestCase):
    def setUp(self):
        self.entite = Entite.objects.create(
            code="nav-test",
            nom="Entite navigation",
            regime=Entite.Regime.COHORTE,
        )

    def creer_utilisateur(self, nom, role):
        return Utilisateur.objects.create_user(
            username=nom,
            email=f"{nom}@example.test",
            password="mot-de-passe-de-test",
            role=role,
            entite=self.entite,
        )

    def verifier_liens_presents(self, reponse, routes):
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.content.count(b'class="barre-laterale"'), 1)
        for route in routes:
            self.assertContains(reponse, reverse(route))

    def test_navigation_etudiant_reste_complete_sur_ses_pages(self):
        etudiant = self.creer_utilisateur("nav-etudiant", Utilisateur.Role.ETUDIANT)
        self.client.force_login(etudiant)
        routes_etudiant = (
            "comptes:tableau_de_bord",
            "inscriptions:paiement_etudiant",
            "inscriptions:inscription_etudiant",
            "inscriptions:cours_etudiant",
            "notes:resultats_etudiant",
            "notes:calendrier_examens",
            "rapports:actes_etudiant",
            "rapports:proces_verbaux",
            "inscriptions:professeurs_etudiant",
        )

        for page in (
            "comptes:tableau_de_bord",
            "inscriptions:paiement_etudiant",
            "inscriptions:inscription_etudiant",
            "inscriptions:cours_etudiant",
            "notes:resultats_etudiant",
            "notes:calendrier_examens",
            "rapports:actes_etudiant",
            "rapports:proces_verbaux",
            "inscriptions:professeurs_etudiant",
        ):
            with self.subTest(page=page):
                reponse = self.client.get(reverse(page))
                self.verifier_liens_presents(reponse, routes_etudiant)
                if page == "comptes:tableau_de_bord":
                    self.assertGreaterEqual(
                        reponse.content.count(
                            reverse("inscriptions:paiement_etudiant").encode()
                        ),
                        2,
                    )

    def test_navigation_professeur_reste_complete_sur_ses_pages(self):
        professeur = self.creer_utilisateur(
            "nav-professeur", Utilisateur.Role.PROFESSEUR
        )
        self.client.force_login(professeur)
        routes_professeur = (
            "comptes:tableau_de_bord",
            "inscriptions:cours_professeur",
            "inscriptions:etudiants_professeur",
            "notes:calendrier_examens",
        )

        for page in routes_professeur:
            with self.subTest(page=page):
                reponse = self.client.get(reverse(page))
                self.verifier_liens_presents(reponse, routes_professeur)
                if page == "comptes:tableau_de_bord":
                    self.assertGreaterEqual(
                        reponse.content.count(
                            reverse("inscriptions:cours_professeur").encode()
                        ),
                        2,
                    )
                    self.assertGreaterEqual(
                        reponse.content.count(
                            reverse("inscriptions:etudiants_professeur").encode()
                        ),
                        2,
                    )

    def test_lien_etudiants_professeur_est_dans_la_navigation_mobile(self):
        professeur = self.creer_utilisateur(
            "nav-professeur-mobile", Utilisateur.Role.PROFESSEUR
        )
        self.client.force_login(professeur)

        reponse = self.client.get(reverse("comptes:tableau_de_bord"))
        navigation_mobile = (
            reponse.content.decode()
            .split('<nav class="navigation-mobile"', 1)[1]
            .split("</nav>", 1)[0]
        )

        self.assertIn(
            f'href="{reverse("inscriptions:etudiants_professeur")}"',
            navigation_mobile,
        )

    def test_navigation_personnel_reste_complete_sur_ses_pages(self):
        personnel = self.creer_utilisateur("nav-personnel", Utilisateur.Role.PERSONNEL)
        self.client.force_login(personnel)
        routes_personnel = (
            "comptes:tableau_de_bord",
            "inscriptions:paiements_a_verifier",
            "inscriptions:inscriptions_a_traiter",
            "notes:notes_a_publier",
            "notes:calendrier_examens",
            "notes:gestion_examens",
            "referentiels:regles_academiques",
            "rapports:tableau",
            "rapports:gestion_dossiers",
            "rapports:liste_etudiants",
            "rapports:gestion_actes",
            "rapports:gestion_soutenances",
            "rapports:proces_verbaux",
        )

        for page in routes_personnel:
            with self.subTest(page=page):
                reponse = self.client.get(reverse(page))
                self.verifier_liens_presents(reponse, routes_personnel)
                if page == "comptes:tableau_de_bord":
                    self.assertGreaterEqual(
                        reponse.content.count(
                            reverse("inscriptions:paiements_a_verifier").encode()
                        ),
                        2,
                    )
                    self.assertGreaterEqual(
                        reponse.content.count(
                            reverse("rapports:gestion_dossiers").encode()
                        ),
                        2,
                    )

    def test_personnel_sans_entite_recoit_une_explication_du_403(self):
        personnel = Utilisateur.objects.create_user(
            username="personnel-sans-entite",
            email="personnel-sans-entite@example.test",
            password="mot-de-passe-de-test",
            role=Utilisateur.Role.PERSONNEL,
        )
        self.client.force_login(personnel)

        reponse = self.client.get(reverse("inscriptions:paiements_a_verifier"))

        self.assertEqual(reponse.status_code, 403)
        self.assertContains(
            reponse,
            "Votre compte Registrariat n'est rattache a aucune entite",
            status_code=403,
        )
        self.assertNotContains(
            reponse,
            reverse("inscriptions:paiements_a_verifier"),
            status_code=403,
        )


class WorkflowPaiementScolariteTests(TestCase):
    def setUp(self):
        self.entite = Entite.objects.create(
            code="famv",
            nom="Faculte d'agronomie",
            regime=Entite.Regime.COHORTE,
        )
        self.programme = Programme.objects.create(
            entite=self.entite,
            code="agronomie",
            nom="Agronomie",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        self.periode = PeriodeAcademique.objects.create(
            entite=self.entite,
            code="2026-s1",
            nom="Premiere session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
            est_ouverte=True,
        )
        self.tarif = TarifScolarite.objects.create(
            programme=self.programme,
            periode=self.periode,
            montant=Decimal("500.00"),
        )
        self.etudiant = self.creer_utilisateur(
            "etudiant-paiement", Utilisateur.Role.ETUDIANT, self.entite
        )
        self.personnel = self.creer_utilisateur(
            "personnel-famv", Utilisateur.Role.PERSONNEL, self.entite
        )

    def creer_utilisateur(self, nom, role, entite):
        return Utilisateur.objects.create_user(
            username=nom,
            email=f"{nom}@example.test",
            password="mot-de-passe-de-test",
            role=role,
            entite=entite,
        )

    def creer_paiement(
        self,
        etudiant=None,
        reference="REC-001",
        montant=Decimal("250.00"),
        statut=PaiementScolarite.Statut.EN_ATTENTE,
        tarif=None,
        valide_par=None,
        motif_refus="",
    ):
        return PaiementScolarite.objects.create(
            etudiant=etudiant or self.etudiant,
            tarif=tarif or self.tarif,
            montant=montant,
            reference=reference,
            date_paiement=date(2026, 10, 9),
            statut=statut,
            valide_par=valide_par,
            date_validation=timezone.now() if valide_par else None,
            motif_refus=motif_refus,
        )

    def test_etudiant_declare_un_paiement_en_attente(self):
        self.client.force_login(self.etudiant)

        reponse = self.client.post(
            reverse("inscriptions:paiement_etudiant"),
            {
                "tarif": self.tarif.pk,
                "montant": "250.00",
                "reference": "REC-ETUDIANT-1",
                "date_paiement": "2026-10-09",
            },
        )

        self.assertRedirects(reponse, reverse("inscriptions:paiement_etudiant"))
        paiement = PaiementScolarite.objects.get(reference="REC-ETUDIANT-1")
        self.assertEqual(paiement.etudiant, self.etudiant)
        self.assertEqual(paiement.statut, PaiementScolarite.Statut.EN_ATTENTE)
        self.assertTrue(
            JournalAction.objects.filter(
                action="paiement.declare", identifiant_objet=str(paiement.pk)
            ).exists()
        )

    def test_recu_pdf_est_reserve_au_proprietaire_et_aux_paiements_valides(self):
        paiement_valide = self.creer_paiement(
            reference="REC-PDF-VALIDE",
            statut=PaiementScolarite.Statut.VALIDE,
            valide_par=self.personnel,
        )
        paiement_en_attente = self.creer_paiement(reference="REC-PDF-ATTENTE")
        autre_etudiant = self.creer_utilisateur(
            "autre-etudiant-paiement", Utilisateur.Role.ETUDIANT, self.entite
        )
        autre_paiement = self.creer_paiement(
            etudiant=autre_etudiant,
            reference="REC-PDF-AUTRE",
            statut=PaiementScolarite.Statut.VALIDE,
            valide_par=self.personnel,
        )
        self.client.force_login(self.etudiant)

        recu = self.client.get(
            reverse("inscriptions:recu_paiement", args=(paiement_valide.pk,))
        )
        attente = self.client.get(
            reverse("inscriptions:recu_paiement", args=(paiement_en_attente.pk,))
        )
        recu_autrui = self.client.get(
            reverse("inscriptions:recu_paiement", args=(autre_paiement.pk,))
        )

        self.assertEqual(recu["Content-Type"], "application/pdf")
        self.assertTrue(recu.content.startswith(b"%PDF"))
        self.assertGreaterEqual(recu.content.count(b"/Subtype /Image"), 2)
        self.assertEqual(attente.status_code, 404)
        self.assertEqual(recu_autrui.status_code, 404)
        self.assertTrue(
            JournalAction.objects.filter(
                utilisateur=self.etudiant,
                action="paiement.recu_pdf_genere",
                identifiant_objet=str(paiement_valide.pk),
            ).exists()
        )

    def test_registrariat_peut_telecharger_recu_de_son_entite_seulement(self):
        paiement_valide = self.creer_paiement(
            reference="REC-PDF-FAMV",
            statut=PaiementScolarite.Statut.VALIDE,
            valide_par=self.personnel,
        )
        autre_entite = Entite.objects.create(
            code="flapdf", nom="Faculte PDF", regime=Entite.Regime.COHORTE
        )
        autre_programme = Programme.objects.create(
            entite=autre_entite,
            code="langues",
            nom="Langues",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        autre_periode = PeriodeAcademique.objects.create(
            entite=autre_entite,
            code="2026-pdf",
            nom="Session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
        )
        autre_tarif = TarifScolarite.objects.create(
            programme=autre_programme,
            periode=autre_periode,
            montant=Decimal("300"),
        )
        autre_etudiant = self.creer_utilisateur(
            "etudiant-pdf-autre", Utilisateur.Role.ETUDIANT, autre_entite
        )
        autre_paiement = self.creer_paiement(
            etudiant=autre_etudiant,
            tarif=autre_tarif,
            reference="REC-PDF-FLA",
            statut=PaiementScolarite.Statut.VALIDE,
            valide_par=self.personnel,
        )
        self.client.force_login(self.personnel)

        recu_entite = self.client.get(
            reverse("inscriptions:recu_paiement", args=(paiement_valide.pk,))
        )
        recu_autre_entite = self.client.get(
            reverse("inscriptions:recu_paiement", args=(autre_paiement.pk,))
        )

        self.assertEqual(recu_entite["Content-Type"], "application/pdf")
        self.assertEqual(recu_autre_entite.status_code, 404)

    def test_registrariat_ne_voit_que_les_paiements_de_son_entite(self):
        autre_entite = Entite.objects.create(
            code="fla", nom="Faculte de linguistique", regime=Entite.Regime.COHORTE
        )
        autre_programme = Programme.objects.create(
            entite=autre_entite,
            code="linguistique",
            nom="Linguistique",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        autre_periode = PeriodeAcademique.objects.create(
            entite=autre_entite,
            code="2026-s1",
            nom="Premiere session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
            est_ouverte=True,
        )
        autre_tarif = TarifScolarite.objects.create(
            programme=autre_programme,
            periode=autre_periode,
            montant=Decimal("300.00"),
        )
        autre_etudiant = self.creer_utilisateur(
            "etudiant-autre-entite", Utilisateur.Role.ETUDIANT, autre_entite
        )
        self.creer_paiement(reference="REC-FAMV")
        self.creer_paiement(
            etudiant=autre_etudiant,
            tarif=autre_tarif,
            reference="REC-FLA",
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(reverse("inscriptions:paiements_a_verifier"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "REC-FAMV")
        self.assertNotContains(reponse, "REC-FLA")

    def test_personnel_valide_un_paiement_et_laction_est_journalisee(self):
        paiement = self.creer_paiement()
        ProfilEtudiant.objects.create(
            utilisateur=self.etudiant,
            code_etudiant="FAMV-PAY-001",
        )
        self.client.force_login(self.personnel)

        url_decision = reverse("inscriptions:decider_paiement", args=(paiement.pk,))
        reponse_sans_verification = self.client.post(
            url_decision,
            {"decision": PaiementScolarite.Statut.VALIDE},
        )

        self.assertRedirects(
            reponse_sans_verification, reverse("inscriptions:paiements_a_verifier")
        )
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, PaiementScolarite.Statut.EN_ATTENTE)

        reponse_verification = self.client.post(
            reverse("inscriptions:verifier_dossier"),
            {"identifiant": "FAMV-PAY-001", "periode": self.periode.pk},
        )
        self.assertEqual(reponse_verification.status_code, 200)
        self.assertTrue(
            JournalAction.objects.filter(
                utilisateur=self.personnel,
                action="dossier.consulte",
                details__etudiant=self.etudiant.username,
                details__periode=self.periode.code,
            ).exists()
        )

        reponse = self.client.post(
            url_decision,
            {"decision": PaiementScolarite.Statut.VALIDE},
        )

        self.assertRedirects(reponse, reverse("inscriptions:paiements_a_verifier"))
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, PaiementScolarite.Statut.VALIDE)
        self.assertEqual(paiement.valide_par, self.personnel)
        self.assertTrue(
            JournalAction.objects.filter(
                action="paiement.valide", identifiant_objet=str(paiement.pk)
            ).exists()
        )

    def test_refus_exige_un_motif(self):
        paiement = self.creer_paiement()
        self.client.force_login(self.personnel)
        url = reverse("inscriptions:decider_paiement", args=(paiement.pk,))

        reponse = self.client.post(url, {"decision": PaiementScolarite.Statut.REFUSE})

        self.assertRedirects(reponse, reverse("inscriptions:paiements_a_verifier"))
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, PaiementScolarite.Statut.EN_ATTENTE)

        self.client.post(
            url,
            {
                "decision": PaiementScolarite.Statut.REFUSE,
                "motif_refus": "Reference illisible",
            },
        )
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, PaiementScolarite.Statut.REFUSE)
        self.assertEqual(paiement.motif_refus, "Reference illisible")

    def test_seuls_les_paiements_valides_comptent_dans_le_total(self):
        self.creer_paiement(
            reference="REC-VALIDE-1",
            montant=Decimal("300.00"),
            statut=PaiementScolarite.Statut.VALIDE,
            valide_par=self.personnel,
        )
        self.creer_paiement(
            reference="REC-ATTENTE",
            montant=Decimal("200.00"),
        )

        total = montant_scolarite_confirme(self.etudiant, self.tarif)

        self.assertEqual(total, Decimal("300.00"))
        self.assertFalse(frais_scolarite_acquittes(self.etudiant, self.tarif))


class WorkflowInscriptionPedagogiqueTests(TestCase):
    def setUp(self):
        self.entite = Entite.objects.create(
            code="famv",
            nom="Faculte d'agronomie",
            regime=Entite.Regime.COHORTE,
        )
        self.programme = Programme.objects.create(
            entite=self.entite,
            code="agronomie",
            nom="Agronomie",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        self.periode = PeriodeAcademique.objects.create(
            entite=self.entite,
            code="2026-s1",
            nom="Premiere session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
            est_ouverte=True,
        )
        self.tarif = TarifScolarite.objects.create(
            programme=self.programme,
            periode=self.periode,
            montant=Decimal("500.00"),
        )
        self.etudiant = self.creer_utilisateur(
            "etudiant-inscription", Utilisateur.Role.ETUDIANT, self.entite
        )
        self.personnel = self.creer_utilisateur(
            "personnel-inscription", Utilisateur.Role.PERSONNEL, self.entite
        )

    def creer_utilisateur(self, nom, role, entite):
        return Utilisateur.objects.create_user(
            username=nom,
            email=f"{nom}@example.test",
            password="mot-de-passe-de-test",
            role=role,
            entite=entite,
        )

    def creer_paiement_valide(self, montant=Decimal("500.00")):
        return PaiementScolarite.objects.create(
            etudiant=self.etudiant,
            tarif=self.tarif,
            montant=montant,
            reference="REC-INSCRIPTION-1",
            date_paiement=date(2026, 10, 9),
            statut=PaiementScolarite.Statut.VALIDE,
            valide_par=self.personnel,
            date_validation=timezone.now(),
        )

    def creer_demande(self):
        return InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
        )

    def test_registrariat_recherche_un_dossier_par_code_nif_ou_cin(self):
        ProfilEtudiant.objects.create(
            utilisateur=self.etudiant,
            code_etudiant="FAMV-2026-001",
            nif="NIF-2026-001",
            cin="CIN-2026-001",
        )
        paiement = self.creer_paiement_valide()
        inscription = InscriptionPedagogique(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
            traite_par=self.personnel,
            date_validation=timezone.now(),
        )
        inscription.full_clean()
        inscription.save()
        self.client.force_login(self.personnel)
        url = reverse("inscriptions:verifier_dossier")

        for identifiant in ("FAMV-2026-001", "NIF-2026-001", "CIN-2026-001"):
            with self.subTest(identifiant=identifiant):
                reponse = self.client.post(
                    url,
                    {"identifiant": identifiant, "periode": self.periode.pk},
                )

                self.assertEqual(reponse.status_code, 200)
                self.assertContains(reponse, self.etudiant.username)
                self.assertContains(reponse, "Acquittes")
                self.assertContains(reponse, "Resultat academique")
                self.assertContains(reponse, "En attente de notes ou de regle")
                self.assertContains(reponse, "Verifiees par le Registrariat")
                self.assertContains(
                    reponse,
                    reverse("inscriptions:fiche_inscription", args=(inscription.pk,)),
                )
                self.assertContains(
                    reponse,
                    reverse("inscriptions:recu_paiement", args=(paiement.pk,)),
                )

        self.assertEqual(
            JournalAction.objects.filter(
                utilisateur=self.personnel,
                action="dossier.consulte",
                identifiant_objet=str(self.etudiant.profil_etudiant.pk),
            ).count(),
            3,
        )

    def test_recherche_dossier_refuse_identifiants_ambigus(self):
        ProfilEtudiant.objects.create(
            utilisateur=self.etudiant,
            code_etudiant="FAMV-AMB-001",
            nif="NIF-DUPLIQUE",
        )
        second_etudiant = self.creer_utilisateur(
            "etudiant-ambiguous", Utilisateur.Role.ETUDIANT, self.entite
        )
        ProfilEtudiant.objects.create(
            utilisateur=second_etudiant,
            code_etudiant="FAMV-AMB-002",
            nif="NIF-DUPLIQUE",
        )
        self.client.force_login(self.personnel)

        reponse = self.client.post(
            reverse("inscriptions:verifier_dossier"),
            {"identifiant": "NIF-DUPLIQUE", "periode": self.periode.pk},
        )

        self.assertContains(reponse, "correspond a plusieurs dossiers")
        self.assertNotContains(reponse, self.etudiant.username)
        self.assertFalse(
            JournalAction.objects.filter(action="dossier.consulte").exists()
        )

    def test_recherche_dossier_est_limitee_au_registrariat_de_l_entite(self):
        ProfilEtudiant.objects.create(
            utilisateur=self.etudiant,
            code_etudiant="FAMV-PRIVE-001",
        )
        autre_entite = Entite.objects.create(
            code="fla-verif",
            nom="Faculte de linguistique",
            regime=Entite.Regime.COHORTE,
        )
        autre_personnel = self.creer_utilisateur(
            "personnel-autre-entite", Utilisateur.Role.PERSONNEL, autre_entite
        )
        self.client.force_login(autre_personnel)

        reponse = self.client.post(
            reverse("inscriptions:verifier_dossier"),
            {"identifiant": "FAMV-PRIVE-001", "periode": self.periode.pk},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertNotContains(reponse, self.etudiant.username)
        self.assertContains(reponse, "Periode academique")
        self.assertFalse(
            JournalAction.objects.filter(action="dossier.consulte").exists()
        )

    def test_etudiant_ne_peut_pas_consulter_le_dossier_par_la_recherche_registrariat(
        self,
    ):
        self.client.force_login(self.etudiant)

        reponse = self.client.get(
            reverse("inscriptions:verifier_dossier"),
            {"identifiant": self.etudiant.username, "periode": self.periode.pk},
        )

        self.assertEqual(reponse.status_code, 403)

    def test_etudiant_ne_peut_pas_sinscrire_sans_frais_valides(self):
        self.client.force_login(self.etudiant)

        reponse = self.client.post(
            reverse("inscriptions:inscription_etudiant"),
            {"programme": self.programme.pk, "periode": self.periode.pk},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "frais doivent etre integralement valides")
        self.assertFalse(InscriptionPedagogique.objects.exists())

    def test_fiche_inscription_imprimable_contient_photo_donnees_et_cours(self):
        ProfilEtudiant.objects.create(
            utilisateur=self.etudiant,
            code_etudiant="FAMV-FICHE-001",
            nif="NIF-FICHE-001",
            cin="CIN-FICHE-001",
            sexe=ProfilEtudiant.Sexe.FEMININ,
            telephone="50900000000",
            adresse="Port-au-Prince",
        )
        cours = Cours.objects.create(
            programme=self.programme,
            code="AGR101",
            nom="Agronomie generale",
            est_obligatoire=True,
        )
        AffectationCours.objects.create(
            professeur=self.creer_utilisateur(
                "professeur-fiche", Utilisateur.Role.PROFESSEUR, self.entite
            ),
            cours=cours,
            periode=self.periode,
        )
        paiement = self.creer_paiement_valide()
        inscription = InscriptionPedagogique(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
            traite_par=self.personnel,
            date_validation=timezone.now(),
        )
        inscription.full_clean()
        inscription.save()
        SelectionCours.objects.create(inscription=inscription, cours=cours)
        self.client.force_login(self.etudiant)

        reponse = self.client.get(
            reverse("inscriptions:fiche_inscription", args=(inscription.pk,))
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Fiche d'inscription pedagogique")
        self.assertContains(reponse, "FAMV-FICHE-001")
        self.assertContains(reponse, "NIF-FICHE-001")
        self.assertContains(reponse, "CIN-FICHE-001")
        self.assertContains(reponse, "AGR101")
        self.assertContains(reponse, "Photo non disponible")
        self.assertContains(reponse, "window.print()")
        self.assertTrue(
            JournalAction.objects.filter(
                utilisateur=self.etudiant,
                action="inscription.fiche_imprimee",
                identifiant_objet=str(inscription.pk),
            ).exists()
        )
        self.assertTrue(PaiementScolarite.objects.filter(pk=paiement.pk).exists())

    def test_fiche_inscription_refuse_inscription_non_validee_ou_sans_paiement_complet(
        self,
    ):
        self.client.force_login(self.etudiant)
        inscription = self.creer_demande()
        url = reverse("inscriptions:fiche_inscription", args=(inscription.pk,))

        self.assertEqual(self.client.get(url).status_code, 404)

        self.creer_paiement_valide(montant=Decimal("250.00"))
        inscription.statut = InscriptionPedagogique.Statut.VALIDEE
        inscription.conditions_passage_verifiees = True
        inscription.traite_par = self.personnel
        inscription.date_validation = timezone.now()
        inscription.save()

        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Paiement incomplet")
        self.assertContains(reponse, "250.00 HTG sur 500.00 HTG")

    def test_fiche_inscription_est_limitee_a_etudiant_ou_registrariat_de_entite(self):
        self.creer_paiement_valide()
        inscription = InscriptionPedagogique(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
            traite_par=self.personnel,
            date_validation=timezone.now(),
        )
        inscription.full_clean()
        inscription.save()
        autre_entite = Entite.objects.create(
            code="fla-fiche",
            nom="Faculte de linguistique",
            regime=Entite.Regime.COHORTE,
        )
        autre_personnel = self.creer_utilisateur(
            "personnel-fiche-autre", Utilisateur.Role.PERSONNEL, autre_entite
        )
        self.client.force_login(autre_personnel)

        reponse = self.client.get(
            reverse("inscriptions:fiche_inscription", args=(inscription.pk,))
        )

        self.assertEqual(reponse.status_code, 404)

    def test_demande_apres_paiement_reste_en_attente(self):
        self.creer_paiement_valide()
        self.client.force_login(self.etudiant)

        reponse = self.client.post(
            reverse("inscriptions:inscription_etudiant"),
            {"programme": self.programme.pk, "periode": self.periode.pk},
        )

        self.assertRedirects(reponse, reverse("inscriptions:inscription_etudiant"))
        inscription = InscriptionPedagogique.objects.get(etudiant=self.etudiant)
        self.assertEqual(inscription.statut, InscriptionPedagogique.Statut.EN_ATTENTE)
        self.assertFalse(inscription.conditions_passage_verifiees)
        self.assertTrue(
            JournalAction.objects.filter(
                action="inscription.soumise", identifiant_objet=str(inscription.pk)
            ).exists()
        )

    def test_validation_exige_paiement_et_confirmation_des_conditions(self):
        self.creer_paiement_valide()
        inscription = self.creer_demande()
        self.client.force_login(self.personnel)
        url = reverse("inscriptions:decider_inscription", args=(inscription.pk,))

        reponse = self.client.post(
            url, {"decision": InscriptionPedagogique.Statut.VALIDEE}
        )

        self.assertRedirects(reponse, reverse("inscriptions:inscriptions_a_traiter"))
        inscription.refresh_from_db()
        self.assertEqual(inscription.statut, InscriptionPedagogique.Statut.EN_ATTENTE)

        self.client.post(
            url,
            {
                "decision": InscriptionPedagogique.Statut.VALIDEE,
                "conditions_passage_verifiees": "on",
            },
        )
        inscription.refresh_from_db()
        self.assertEqual(inscription.statut, InscriptionPedagogique.Statut.VALIDEE)
        self.assertTrue(inscription.conditions_passage_verifiees)
        self.assertEqual(inscription.traite_par, self.personnel)
        self.assertTrue(
            JournalAction.objects.filter(
                action="inscription.validee", identifiant_objet=str(inscription.pk)
            ).exists()
        )

    def test_registrariat_recontrole_le_paiement_au_moment_de_valider(self):
        inscription = self.creer_demande()
        self.client.force_login(self.personnel)

        reponse = self.client.post(
            reverse("inscriptions:decider_inscription", args=(inscription.pk,)),
            {
                "decision": InscriptionPedagogique.Statut.VALIDEE,
                "conditions_passage_verifiees": "on",
            },
        )

        self.assertRedirects(reponse, reverse("inscriptions:inscriptions_a_traiter"))
        inscription.refresh_from_db()
        self.assertEqual(inscription.statut, InscriptionPedagogique.Statut.EN_ATTENTE)

    def test_refus_exige_un_motif_et_est_journalise(self):
        inscription = self.creer_demande()
        self.client.force_login(self.personnel)
        url = reverse("inscriptions:decider_inscription", args=(inscription.pk,))

        self.client.post(url, {"decision": InscriptionPedagogique.Statut.REFUSEE})
        inscription.refresh_from_db()
        self.assertEqual(inscription.statut, InscriptionPedagogique.Statut.EN_ATTENTE)

        self.client.post(
            url,
            {
                "decision": InscriptionPedagogique.Statut.REFUSEE,
                "motif_decision": "Conditions de passage non remplies",
            },
        )
        inscription.refresh_from_db()
        self.assertEqual(inscription.statut, InscriptionPedagogique.Statut.REFUSEE)
        self.assertTrue(
            JournalAction.objects.filter(
                action="inscription.refusee", identifiant_objet=str(inscription.pk)
            ).exists()
        )

    def test_queue_registrariat_est_limitee_a_son_entite(self):
        autre_entite = Entite.objects.create(
            code="fla", nom="Faculte de linguistique", regime=Entite.Regime.COHORTE
        )
        autre_programme = Programme.objects.create(
            entite=autre_entite,
            code="linguistique",
            nom="Linguistique",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        autre_periode = PeriodeAcademique.objects.create(
            entite=autre_entite,
            code="2026-s1",
            nom="Premiere session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
        )
        autre_etudiant = self.creer_utilisateur(
            "etudiant-autre-entite", Utilisateur.Role.ETUDIANT, autre_entite
        )
        InscriptionPedagogique.objects.create(
            etudiant=autre_etudiant,
            programme=autre_programme,
            periode=autre_periode,
        )
        self.creer_demande()
        self.client.force_login(self.personnel)

        reponse = self.client.get(reverse("inscriptions:inscriptions_a_traiter"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.etudiant.username)
        self.assertNotContains(reponse, autre_etudiant.username)


class ChoixCoursEtudiantTests(TestCase):
    def setUp(self):
        self.entite = Entite.objects.create(
            code="famv",
            nom="Faculte d'agronomie",
            regime=Entite.Regime.COHORTE,
        )
        self.programme = Programme.objects.create(
            entite=self.entite,
            code="agronomie",
            nom="Agronomie",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        self.periode = PeriodeAcademique.objects.create(
            entite=self.entite,
            code="2026-s1",
            nom="Premiere session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
            est_ouverte=True,
        )
        self.tarif = TarifScolarite.objects.create(
            programme=self.programme,
            periode=self.periode,
            montant=Decimal("500.00"),
        )
        self.etudiant = self.creer_utilisateur(
            "etudiant-cours", Utilisateur.Role.ETUDIANT
        )
        self.personnel = self.creer_utilisateur(
            "personnel-cours", Utilisateur.Role.PERSONNEL
        )
        self.professeur = self.creer_utilisateur(
            "professeur-cours", Utilisateur.Role.PROFESSEUR
        )
        self.cours_obligatoire = Cours.objects.create(
            programme=self.programme,
            code="AGR101",
            nom="Agronomie generale",
            est_obligatoire=True,
        )
        self.cours_optionnel = Cours.objects.create(
            programme=self.programme,
            code="BIO101",
            nom="Biologie generale",
            est_obligatoire=False,
        )
        self.cours_non_offert = Cours.objects.create(
            programme=self.programme,
            code="MAT101",
            nom="Mathematiques",
            est_obligatoire=False,
        )
        for cours in (self.cours_obligatoire, self.cours_optionnel):
            AffectationCours.objects.create(
                professeur=self.professeur,
                cours=cours,
                periode=self.periode,
            )
        self.paiement = PaiementScolarite.objects.create(
            etudiant=self.etudiant,
            tarif=self.tarif,
            montant=Decimal("500.00"),
            reference="REC-COURS-1",
            date_paiement=date(2026, 10, 9),
            statut=PaiementScolarite.Statut.VALIDE,
            valide_par=self.personnel,
            date_validation=timezone.now(),
        )
        self.inscription = InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
            traite_par=self.personnel,
            date_validation=timezone.now(),
        )

    def creer_utilisateur(self, nom, role):
        return Utilisateur.objects.create_user(
            username=nom,
            email=f"{nom}@example.test",
            password="mot-de-passe-de-test",
            role=role,
            entite=self.entite,
        )

    def test_page_ne_propose_que_les_cours_affectes_a_la_periode(self):
        self.client.force_login(self.etudiant)

        reponse = self.client.get(
            reverse(
                "inscriptions:choix_cours_etudiant",
                args=(self.inscription.pk,),
            )
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.cours_obligatoire.code)
        self.assertContains(reponse, self.cours_optionnel.code)
        self.assertNotContains(reponse, self.cours_non_offert.code)

    def test_tarif_desactive_ne_bloque_pas_une_inscription_deja_payee(self):
        self.tarif.est_actif = False
        self.tarif.save(update_fields=("est_actif",))
        self.client.force_login(self.etudiant)

        page_cours = self.client.get(
            reverse("inscriptions:choix_cours_etudiant", args=(self.inscription.pk,))
        )
        page_fiche = self.client.get(
            reverse("inscriptions:fiche_inscription", args=(self.inscription.pk,))
        )

        self.assertEqual(page_cours.status_code, 200)
        self.assertContains(page_cours, self.cours_obligatoire.code)
        self.assertEqual(page_fiche.status_code, 200)
        self.assertContains(page_fiche, "Fiche d'inscription pedagogique")

    def test_tarif_absent_affiche_une_explication_sur_les_deux_pages(self):
        self.paiement.delete()
        self.tarif.delete()
        self.client.force_login(self.etudiant)

        for route in (
            "inscriptions:choix_cours_etudiant",
            "inscriptions:fiche_inscription",
        ):
            with self.subTest(route=route):
                reponse = self.client.get(reverse(route, args=(self.inscription.pk,)))

                self.assertEqual(reponse.status_code, 200)
                self.assertContains(reponse, "Tarif introuvable")
                self.assertContains(reponse, "Contactez le Registrariat")
                self.assertNotContains(reponse, "No TarifScolarite matches")

    def test_paiement_partiel_affiche_le_montant_restant_sur_les_deux_pages(self):
        self.paiement.montant = Decimal("250.00")
        self.paiement.save(update_fields=("montant",))
        self.client.force_login(self.etudiant)

        for route in (
            "inscriptions:choix_cours_etudiant",
            "inscriptions:fiche_inscription",
        ):
            with self.subTest(route=route):
                reponse = self.client.get(reverse(route, args=(self.inscription.pk,)))

                self.assertEqual(reponse.status_code, 200)
                self.assertContains(reponse, "Paiement incomplet")
                self.assertContains(reponse, "250.00 HTG sur 500.00 HTG")

    def test_tous_les_cours_obligatoires_sont_requis(self):
        self.client.force_login(self.etudiant)

        reponse = self.client.post(
            reverse(
                "inscriptions:choix_cours_etudiant",
                args=(self.inscription.pk,),
            ),
            {"cours": [self.cours_optionnel.pk]},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Tous les cours obligatoires offerts")
        self.assertFalse(
            SelectionCours.objects.filter(inscription=self.inscription).exists()
        )

    def test_etudiant_peut_enregistrer_les_cours_offerts(self):
        self.client.force_login(self.etudiant)

        reponse = self.client.post(
            reverse(
                "inscriptions:choix_cours_etudiant",
                args=(self.inscription.pk,),
            ),
            {"cours": [self.cours_obligatoire.pk, self.cours_optionnel.pk]},
        )

        self.assertRedirects(
            reponse,
            reverse(
                "inscriptions:choix_cours_etudiant",
                args=(self.inscription.pk,),
            ),
        )
        self.assertEqual(
            SelectionCours.objects.filter(inscription=self.inscription).count(), 2
        )
        self.assertTrue(
            JournalAction.objects.filter(
                action="inscription.cours_modifies",
                identifiant_objet=str(self.inscription.pk),
            ).exists()
        )

    def test_inscription_non_validee_ne_peut_pas_acceder_aux_cours(self):
        inscription_en_attente = InscriptionPedagogique.objects.create(
            etudiant=self.creer_utilisateur(
                "etudiant-en-attente-cours", Utilisateur.Role.ETUDIANT
            ),
            programme=self.programme,
            periode=self.periode,
        )
        self.client.force_login(inscription_en_attente.etudiant)

        reponse = self.client.get(
            reverse(
                "inscriptions:choix_cours_etudiant",
                args=(inscription_en_attente.pk,),
            )
        )

        self.assertEqual(reponse.status_code, 404)

    def test_periode_fermee_interdit_les_modifications(self):
        self.periode.est_ouverte = False
        self.periode.save(update_fields=("est_ouverte",))
        self.client.force_login(self.etudiant)

        reponse = self.client.post(
            reverse(
                "inscriptions:choix_cours_etudiant",
                args=(self.inscription.pk,),
            ),
            {"cours": [self.cours_obligatoire.pk]},
        )

        self.assertRedirects(
            reponse,
            reverse(
                "inscriptions:choix_cours_etudiant",
                args=(self.inscription.pk,),
            ),
        )
        self.assertFalse(
            SelectionCours.objects.filter(inscription=self.inscription).exists()
        )
