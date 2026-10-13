from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from applications.audit.models import JournalAction
from applications.comptes.models import ProfilEtudiant, Utilisateur
from applications.inscriptions.models import (
    InscriptionPedagogique,
    PaiementScolarite,
    SelectionCours,
    TarifScolarite,
)
from applications.notes.models import Evaluation
from applications.rapports.models import (
    ActeAcademique,
    DossierEtudes,
    SoutenanceMemoire,
)
from applications.rapports.documents import generer_pdf_acte
from applications.rapports.services import calculer_indicateurs
from applications.rapports.services import calculer_statistiques_cours
from applications.referentiels.models import (
    Cours,
    Entite,
    PeriodeAcademique,
    Programme,
    RegleAcademique,
)


class RapportsAcademiquesTests(TestCase):
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
        self.personnel = self.creer_utilisateur(
            "personnel-rapports", Utilisateur.Role.PERSONNEL, self.entite
        )
        self.etudiant = self.creer_utilisateur(
            "etudiant-rapports", Utilisateur.Role.ETUDIANT, self.entite
        )
        ProfilEtudiant.objects.create(
            utilisateur=self.etudiant,
            code_etudiant="FAMV-001",
            sexe=ProfilEtudiant.Sexe.FEMININ,
        )

    def creer_utilisateur(self, nom, role, entite):
        return Utilisateur.objects.create_user(
            username=nom,
            email=f"{nom}@example.test",
            password="mot-de-passe-de-test",
            role=role,
            entite=entite,
        )

    def test_personnel_voit_les_statistiques_de_son_entite(self):
        InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
        )
        DossierEtudes.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            statut=DossierEtudes.Statut.EN_COURS,
            date_ouverture=date(2026, 9, 1),
            cree_par=self.personnel,
        )
        ActeAcademique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            type_acte=ActeAcademique.TypeActe.DIPLOME,
            reference="DIP-FAMV-001",
            date_delivrance=date(2026, 10, 1),
            delivre_par=self.personnel,
        )
        SoutenanceMemoire.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            titre="Etude agronomique",
            date_soutenance=date(2026, 10, 1),
            statut=SoutenanceMemoire.Statut.SOUTENUE,
            note=80,
            enregistre_par=self.personnel,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:tableau"),
            {"periode": self.periode.pk, "programme": self.programme.pk},
        )

        self.assertEqual(reponse.status_code, 200)
        indicateurs = reponse.context["indicateurs"]
        self.assertEqual(indicateurs["nombre_etudiants"], 1)
        self.assertEqual(indicateurs["nombre_profils_renseignes"], 1)
        self.assertEqual(indicateurs["nombre_diplomes"], 1)
        self.assertEqual(indicateurs["nombre_soutenances"], 1)
        self.assertEqual(
            indicateurs["repartition_dossiers_sexe"],
            [
                {
                    "statut": DossierEtudes.Statut.EN_COURS,
                    "sexe": ProfilEtudiant.Sexe.FEMININ,
                    "nombre": 1,
                    "statut_display": DossierEtudes.Statut.EN_COURS.label,
                    "sexe_display": ProfilEtudiant.Sexe.FEMININ.label,
                }
            ],
        )
        self.assertEqual(
            indicateurs["repartition_actes_sexe"],
            [
                {
                    "type_acte": ActeAcademique.TypeActe.DIPLOME,
                    "sexe": ProfilEtudiant.Sexe.FEMININ,
                    "nombre": 1,
                    "type_acte_display": ActeAcademique.TypeActe.DIPLOME.label,
                    "sexe_display": ProfilEtudiant.Sexe.FEMININ.label,
                }
            ],
        )
        self.assertEqual(
            indicateurs["repartition_soutenances_sexe"],
            [
                {
                    "sexe": ProfilEtudiant.Sexe.FEMININ,
                    "nombre": 1,
                    "sexe_display": ProfilEtudiant.Sexe.FEMININ.label,
                }
            ],
        )

    def test_note_eliminatoire_prime_sur_une_moyenne_de_reprise(self):
        self.periode.date_debut = date(2026, 9, 1)
        self.periode.save(update_fields=("date_debut",))
        RegleAcademique.objects.create(
            entite=self.entite,
            version="reglement-note-eliminatoire",
            date_effet=date(2026, 8, 1),
            parametres={
                "seuil_reussite_cours": "65",
                "seuil_reprise_cours": "60",
                "note_eliminatoire": "40",
            },
        )
        cours = Cours.objects.create(
            programme=self.programme,
            code="BIO-ELIM",
            nom="Evaluation eliminatoire",
        )
        for libelle, note in (("Devoir", 90), ("Examen eliminatoire", 39)):
            Evaluation.objects.create(
                etudiant=self.etudiant,
                cours=cours,
                periode=self.periode,
                libelle=libelle,
                note=Decimal(str(note)),
                coefficient=Decimal("1"),
                est_publiee=True,
                saisie_par=self.personnel,
            )

        statistiques = calculer_statistiques_cours(self.entite)

        self.assertEqual(statistiques[0]["reprises"], 0)
        self.assertEqual(statistiques[0]["echecs"], 1)

    def test_compte_les_sexes_non_renseignes_avec_ou_sans_profil(self):
        etudiant_profil_incomplet = self.creer_utilisateur(
            "etudiant-profil-incomplet", Utilisateur.Role.ETUDIANT, self.entite
        )
        ProfilEtudiant.objects.create(utilisateur=etudiant_profil_incomplet)
        self.creer_utilisateur(
            "etudiant-sans-profil", Utilisateur.Role.ETUDIANT, self.entite
        )

        indicateurs = calculer_indicateurs(self.entite)

        self.assertEqual(indicateurs["nombre_sexe_non_renseigne"], 2)

    def test_statistiques_cours_utilisent_la_regle_effective_et_le_sexe(self):
        self.periode.date_debut = date(2026, 9, 1)
        self.periode.save(update_fields=("date_debut",))
        RegleAcademique.objects.create(
            entite=self.entite,
            version="reglement-ancien",
            date_effet=date(2025, 1, 1),
            parametres={"seuil_reussite_cours": 50},
        )
        RegleAcademique.objects.create(
            entite=self.entite,
            version="reglement-actuel",
            date_effet=date(2026, 8, 1),
            parametres={
                "seuil_reussite_cours": 65,
                "seuil_reprise_cours": 60,
            },
        )
        RegleAcademique.objects.create(
            entite=self.entite,
            version="reglement-futur",
            date_effet=date(2026, 10, 1),
            parametres={"seuil_reussite_cours": 90},
        )
        cours = Cours.objects.create(
            programme=self.programme,
            code="BIO101",
            nom="Biologie generale",
        )
        autre_etudiant = self.creer_utilisateur(
            "etudiant-echec-cours", Utilisateur.Role.ETUDIANT, self.entite
        )
        ProfilEtudiant.objects.create(
            utilisateur=autre_etudiant,
            code_etudiant="FAMV-002",
            sexe=ProfilEtudiant.Sexe.MASCULIN,
        )
        etudiant_reprise = self.creer_utilisateur(
            "etudiant-reprise-cours", Utilisateur.Role.ETUDIANT, self.entite
        )
        ProfilEtudiant.objects.create(
            utilisateur=etudiant_reprise,
            code_etudiant="FAMV-003",
            sexe=ProfilEtudiant.Sexe.AUTRE,
        )
        for libelle, note in (("Devoir", 70), ("Examen", 60)):
            Evaluation.objects.create(
                etudiant=self.etudiant,
                cours=cours,
                periode=self.periode,
                libelle=libelle,
                note=note,
                coefficient=1,
                est_publiee=True,
                saisie_par=self.personnel,
            )
        Evaluation.objects.create(
            etudiant=autre_etudiant,
            cours=cours,
            periode=self.periode,
            libelle="Examen",
            note=59,
            coefficient=1,
            est_publiee=True,
            saisie_par=self.personnel,
        )
        Evaluation.objects.create(
            etudiant=etudiant_reprise,
            cours=cours,
            periode=self.periode,
            libelle="Examen",
            note=60,
            coefficient=1,
            est_publiee=True,
            saisie_par=self.personnel,
        )

        statistiques = calculer_statistiques_cours(self.entite)

        self.assertEqual(len(statistiques), 1)
        self.assertEqual(statistiques[0]["seuil_reussite"], Decimal("65"))
        self.assertEqual(statistiques[0]["seuil_reprise"], Decimal("60"))
        self.assertEqual(statistiques[0]["version_regle"], "reglement-actuel")
        self.assertEqual(statistiques[0]["nombre_etudiants"], 3)
        self.assertEqual(statistiques[0]["reussites"], 1)
        self.assertEqual(statistiques[0]["reprises"], 1)
        self.assertEqual(statistiques[0]["echecs"], 1)
        self.assertEqual(
            statistiques[0]["repartition_sexe"],
            [
                {
                    "sexe": ProfilEtudiant.Sexe.AUTRE,
                    "sexe_display": ProfilEtudiant.Sexe.AUTRE.label,
                    "reussites": 0,
                    "reprises": 1,
                    "echecs": 0,
                },
                {
                    "sexe": ProfilEtudiant.Sexe.FEMININ,
                    "sexe_display": ProfilEtudiant.Sexe.FEMININ.label,
                    "reussites": 1,
                    "reprises": 0,
                    "echecs": 0,
                },
                {
                    "sexe": ProfilEtudiant.Sexe.MASCULIN,
                    "sexe_display": ProfilEtudiant.Sexe.MASCULIN.label,
                    "reussites": 0,
                    "reprises": 0,
                    "echecs": 1,
                },
            ],
        )
        self.client.force_login(self.personnel)
        reponse = self.client.get(
            reverse("rapports:tableau"),
            {"periode": self.periode.pk, "programme": self.programme.pk},
        )
        self.assertContains(reponse, "Reussites, reprises et echecs par cours")
        self.assertContains(reponse, "reglement-actuel")
        export = self.client.get(
            reverse("rapports:exporter_csv"),
            {"periode": self.periode.pk, "programme": self.programme.pk},
        )
        self.assertContains(export, "BIO101")
        self.assertContains(export, "Reussites")
        self.assertContains(export, "Reprises")

    def test_statistiques_cours_ne_deviennent_pas_des_decisions_sans_seuil(self):
        self.periode.date_debut = date(2026, 9, 1)
        self.periode.save(update_fields=("date_debut",))
        cours = Cours.objects.create(
            programme=self.programme,
            code="BIO102",
            nom="Ecologie",
        )
        Evaluation.objects.create(
            etudiant=self.etudiant,
            cours=cours,
            periode=self.periode,
            libelle="Examen",
            note=80,
            coefficient=1,
            est_publiee=True,
            saisie_par=self.personnel,
        )

        statistiques = calculer_statistiques_cours(self.entite)

        self.assertIsNone(statistiques[0]["seuil_reussite"])
        self.assertIsNone(statistiques[0]["seuil_reprise"])
        self.assertIsNone(statistiques[0]["reussites"])
        self.assertIsNone(statistiques[0]["reprises"])
        self.assertIsNone(statistiques[0]["echecs"])

    def test_export_csv_conserve_le_filtre_et_les_aggregats(self):
        InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.EN_ATTENTE,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:exporter_csv"),
            {"periode": self.periode.pk, "programme": self.programme.pk},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("text/csv", reponse["Content-Type"])
        self.assertIn("Inscriptions en attente", reponse.content.decode("utf-8-sig"))
        self.assertIn(",1", reponse.content.decode("utf-8-sig"))

    def test_personnel_ne_peut_pas_lire_une_autre_entite(self):
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
            "etudiant-fla-rapports", Utilisateur.Role.ETUDIANT, autre_entite
        )
        ProfilEtudiant.objects.create(
            utilisateur=autre_etudiant,
            code_etudiant="FLA-001",
            sexe=ProfilEtudiant.Sexe.MASCULIN,
        )
        InscriptionPedagogique.objects.create(
            etudiant=autre_etudiant,
            programme=autre_programme,
            periode=autre_periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:tableau"), {"entite": autre_entite.pk}
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["entite"], self.entite)
        self.assertEqual(reponse.context["indicateurs"]["nombre_etudiants"], 1)

    def test_etudiant_naccede_pas_aux_statistiques_globales(self):
        self.client.force_login(self.etudiant)

        reponse = self.client.get(reverse("rapports:tableau"))

        self.assertEqual(reponse.status_code, 403)

    def test_etudiant_ne_voit_et_nimprime_que_ses_actes(self):
        acte_personnel = ActeAcademique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            type_acte=ActeAcademique.TypeActe.CERTIFICAT,
            reference="CERT-FAMV-001",
            date_delivrance=date(2026, 10, 1),
            delivre_par=self.personnel,
        )
        autre_etudiant = self.creer_utilisateur(
            "autre-etudiant-famv", Utilisateur.Role.ETUDIANT, self.entite
        )
        acte_autrui = ActeAcademique.objects.create(
            etudiant=autre_etudiant,
            programme=self.programme,
            periode=self.periode,
            type_acte=ActeAcademique.TypeActe.CERTIFICAT,
            reference="CERT-FAMV-002",
            date_delivrance=date(2026, 10, 1),
            delivre_par=self.personnel,
        )
        self.client.force_login(self.etudiant)

        liste = self.client.get(reverse("rapports:actes_etudiant"))
        impression_personnelle = self.client.get(
            reverse("rapports:acte_imprimable", args=(acte_personnel.pk,))
        )
        impression_autrui = self.client.get(
            reverse("rapports:acte_imprimable", args=(acte_autrui.pk,))
        )
        pdf_personnel = self.client.get(
            reverse("rapports:telecharger_acte_pdf", args=(acte_personnel.pk,))
        )
        pdf_autrui = self.client.get(
            reverse("rapports:telecharger_acte_pdf", args=(acte_autrui.pk,))
        )

        self.assertContains(liste, acte_personnel.reference)
        self.assertNotContains(liste, acte_autrui.reference)
        self.assertEqual(impression_personnelle.status_code, 200)
        self.assertEqual(impression_autrui.status_code, 404)
        self.assertEqual(pdf_personnel["Content-Type"], "application/pdf")
        self.assertTrue(pdf_personnel.content.startswith(b"%PDF"))
        self.assertGreaterEqual(pdf_personnel.content.count(b"/Subtype /Image"), 2)
        self.assertEqual(pdf_autrui.status_code, 404)
        self.assertTrue(
            JournalAction.objects.filter(
                utilisateur=self.etudiant,
                action="acte.pdf_genere",
                identifiant_objet=str(acte_personnel.pk),
            ).exists()
        )

    def test_pdf_releve_contient_les_notes_publiees_seulement(self):
        cours = Cours.objects.create(
            programme=self.programme,
            code="BIO101",
            nom="Biologie generale",
        )
        Evaluation.objects.create(
            etudiant=self.etudiant,
            cours=cours,
            periode=self.periode,
            libelle="Examen publie",
            note=82,
            coefficient=1,
            est_publiee=True,
            saisie_par=self.personnel,
        )
        Evaluation.objects.create(
            etudiant=self.etudiant,
            cours=cours,
            periode=self.periode,
            libelle="Note confidentielle",
            note=20,
            coefficient=1,
            est_publiee=False,
            saisie_par=self.personnel,
        )
        acte = ActeAcademique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            type_acte=ActeAcademique.TypeActe.RELEVE_NOTES,
            reference="REL-FAMV-001",
            date_delivrance=date(2026, 10, 1),
            delivre_par=self.personnel,
        )
        self.client.force_login(self.etudiant)

        reponse = self.client.get(
            reverse("rapports:telecharger_acte_pdf", args=(acte.pk,))
        )

        self.assertEqual(reponse["Content-Type"], "application/pdf")
        self.assertIn(b"BIO101", reponse.content)
        self.assertIn(b"Examen publie", reponse.content)
        self.assertNotIn(b"Note confidentielle", reponse.content)

    def test_chaque_type_d_acte_peut_etre_genere_en_pdf(self):
        for index, type_acte in enumerate(ActeAcademique.TypeActe.values, start=1):
            acte = ActeAcademique.objects.create(
                etudiant=self.etudiant,
                programme=self.programme,
                periode=self.periode,
                type_acte=type_acte,
                reference=f"ACTE-FAMV-{index:03d}",
                date_delivrance=date(2026, 10, 1),
                delivre_par=self.personnel,
            )

            self.assertTrue(generer_pdf_acte(acte).startswith(b"%PDF"))

    def test_etudiant_ne_voit_et_nimprime_que_son_proces_verbal(self):
        proces_verbal = SoutenanceMemoire.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            titre="Etude agronomique personnelle",
            date_soutenance=date(2026, 10, 1),
            statut=SoutenanceMemoire.Statut.SOUTENUE,
            note=80,
            jury="Membres du jury",
            enregistre_par=self.personnel,
        )
        autre_etudiant = self.creer_utilisateur(
            "autre-etudiant-soutenance", Utilisateur.Role.ETUDIANT, self.entite
        )
        proces_verbal_autrui = SoutenanceMemoire.objects.create(
            etudiant=autre_etudiant,
            programme=self.programme,
            periode=self.periode,
            titre="Etude agronomique d'autrui",
            date_soutenance=date(2026, 10, 2),
            statut=SoutenanceMemoire.Statut.SOUTENUE,
            note=75,
            enregistre_par=self.personnel,
        )
        self.client.force_login(self.etudiant)

        liste = self.client.get(reverse("rapports:proces_verbaux"))
        impression_personnelle = self.client.get(
            reverse(
                "rapports:proces_verbal_imprimable",
                args=(proces_verbal.pk,),
            )
        )
        impression_autrui = self.client.get(
            reverse(
                "rapports:proces_verbal_imprimable",
                args=(proces_verbal_autrui.pk,),
            )
        )
        pdf_personnel = self.client.get(
            reverse(
                "rapports:telecharger_proces_verbal_pdf",
                args=(proces_verbal.pk,),
            )
        )
        pdf_autrui = self.client.get(
            reverse(
                "rapports:telecharger_proces_verbal_pdf",
                args=(proces_verbal_autrui.pk,),
            )
        )

        self.assertContains(liste, proces_verbal.titre)
        self.assertNotContains(liste, proces_verbal_autrui.titre)
        self.assertContains(impression_personnelle, "Membres du jury")
        self.assertEqual(impression_autrui.status_code, 404)
        self.assertEqual(pdf_personnel["Content-Type"], "application/pdf")
        self.assertTrue(pdf_personnel.content.startswith(b"%PDF"))
        self.assertGreaterEqual(pdf_personnel.content.count(b"/Subtype /Image"), 2)
        self.assertEqual(pdf_autrui.status_code, 404)
        self.assertTrue(
            JournalAction.objects.filter(
                utilisateur=self.etudiant,
                action="soutenance.pdf_genere",
                identifiant_objet=str(proces_verbal.pk),
            ).exists()
        )

    def test_personnel_ne_voit_que_les_proces_verbaux_de_son_entite(self):
        SoutenanceMemoire.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            titre="Soutenance FAMV",
            date_soutenance=date(2026, 10, 1),
            statut=SoutenanceMemoire.Statut.SOUTENUE,
            note=80,
            enregistre_par=self.personnel,
        )
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
        SoutenanceMemoire.objects.create(
            etudiant=self.etudiant,
            programme=autre_programme,
            periode=autre_periode,
            titre="Soutenance FLA",
            date_soutenance=date(2026, 10, 2),
            statut=SoutenanceMemoire.Statut.SOUTENUE,
            note=75,
            enregistre_par=self.personnel,
        )
        self.client.force_login(self.personnel)

        liste = self.client.get(reverse("rapports:proces_verbaux"))

        self.assertContains(liste, "Soutenance FAMV")
        self.assertNotContains(liste, "Soutenance FLA")

    def test_personnel_emet_un_acte_et_laction_est_journalisee(self):
        self.client.force_login(self.personnel)

        reponse = self.client.post(
            reverse("rapports:gestion_actes"),
            {
                "etudiant": self.etudiant.pk,
                "programme": self.programme.pk,
                "periode": self.periode.pk,
                "type_acte": ActeAcademique.TypeActe.CERTIFICAT,
                "reference": "CERT-FAMV-EMIS-001",
                "date_delivrance": "2026-10-09",
            },
        )

        self.assertRedirects(reponse, reverse("rapports:gestion_actes"))
        acte = ActeAcademique.objects.get(reference="CERT-FAMV-EMIS-001")
        self.assertEqual(acte.delivre_par, self.personnel)
        self.assertTrue(
            JournalAction.objects.filter(
                utilisateur=self.personnel,
                action="acte.delivre",
                identifiant_objet=str(acte.pk),
            ).exists()
        )

    def test_personnel_ne_peut_pas_emettre_un_acte_hors_de_son_entite(self):
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
            "etudiant-fla-acte", Utilisateur.Role.ETUDIANT, autre_entite
        )
        self.client.force_login(self.personnel)

        reponse = self.client.post(
            reverse("rapports:gestion_actes"),
            {
                "etudiant": autre_etudiant.pk,
                "programme": autre_programme.pk,
                "periode": autre_periode.pk,
                "type_acte": ActeAcademique.TypeActe.CERTIFICAT,
                "reference": "CERT-FLA-INTERDIT-001",
                "date_delivrance": "2026-10-09",
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(
            ActeAcademique.objects.filter(reference="CERT-FLA-INTERDIT-001").exists()
        )

    def test_personnel_planifie_et_valide_une_soutenance_avec_audit(self):
        self.client.force_login(self.personnel)
        reponse = self.client.post(
            reverse("rapports:gestion_soutenances"),
            {
                "etudiant": self.etudiant.pk,
                "programme": self.programme.pk,
                "periode": self.periode.pk,
                "titre": "Etude agronomique",
                "date_soutenance": "2026-11-15",
                "statut": SoutenanceMemoire.Statut.PLANIFIEE,
                "note": "",
                "jury": "Jury provisoire",
            },
        )

        self.assertRedirects(reponse, reverse("rapports:gestion_soutenances"))
        soutenance = SoutenanceMemoire.objects.get(titre="Etude agronomique")
        self.assertEqual(soutenance.enregistre_par, self.personnel)
        self.assertTrue(
            JournalAction.objects.filter(
                action="soutenance.planifiee",
                identifiant_objet=str(soutenance.pk),
            ).exists()
        )

        reponse_validation = self.client.post(
            reverse("rapports:modifier_soutenance", args=(soutenance.pk,)),
            {
                "etudiant": self.etudiant.pk,
                "programme": self.programme.pk,
                "periode": self.periode.pk,
                "titre": "Etude agronomique",
                "date_soutenance": "2026-11-15",
                "statut": SoutenanceMemoire.Statut.SOUTENUE,
                "note": "84.50",
                "jury": "Jury confirme",
            },
        )
        self.assertRedirects(
            reponse_validation,
            reverse("rapports:gestion_soutenances"),
        )
        soutenance.refresh_from_db()
        self.assertEqual(soutenance.statut, SoutenanceMemoire.Statut.SOUTENUE)
        self.assertEqual(soutenance.note, Decimal("84.50"))
        self.assertEqual(soutenance.enregistre_par, self.personnel)
        self.assertTrue(
            JournalAction.objects.filter(
                action="soutenance.modifiee",
                identifiant_objet=str(soutenance.pk),
            ).exists()
        )

    def test_personnel_ne_peut_pas_modifier_une_soutenance_hors_entite(self):
        autre_entite = Entite.objects.create(
            code="ierah", nom="IERAH", regime=Entite.Regime.CREDITS
        )
        autre_programme = Programme.objects.create(
            entite=autre_entite,
            code="urbanisme",
            nom="Urbanisme",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        autre_periode = PeriodeAcademique.objects.create(
            entite=autre_entite,
            code="2026-s1",
            nom="Premiere session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
        )
        soutenance = SoutenanceMemoire.objects.create(
            etudiant=self.etudiant,
            programme=autre_programme,
            periode=autre_periode,
            titre="Projet urbain",
            date_soutenance=date(2026, 11, 15),
            statut=SoutenanceMemoire.Statut.PLANIFIEE,
            enregistre_par=self.personnel,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:modifier_soutenance", args=(soutenance.pk,))
        )

        self.assertEqual(reponse.status_code, 404)

    def test_personnel_ouvre_et_cloture_un_dossier_avec_audit(self):
        self.client.force_login(self.personnel)
        reponse = self.client.post(
            reverse("rapports:gestion_dossiers"),
            {
                "etudiant": self.etudiant.pk,
                "programme": self.programme.pk,
                "statut": DossierEtudes.Statut.EN_COURS,
                "date_ouverture": "2026-09-01",
                "date_cloture": "",
                "motif_cloture": "",
            },
        )

        self.assertRedirects(reponse, reverse("rapports:gestion_dossiers"))
        dossier = DossierEtudes.objects.get(etudiant=self.etudiant)
        self.assertEqual(dossier.cree_par, self.personnel)
        self.assertTrue(
            JournalAction.objects.filter(
                action="dossier.cree", identifiant_objet=str(dossier.pk)
            ).exists()
        )

        reponse_cloture = self.client.post(
            reverse("rapports:modifier_dossier", args=(dossier.pk,)),
            {
                "etudiant": self.etudiant.pk,
                "programme": self.programme.pk,
                "statut": DossierEtudes.Statut.DIPLOME,
                "date_ouverture": "2026-09-01",
                "date_cloture": "2027-06-30",
                "motif_cloture": "Diplome confirme par le jury",
            },
        )

        self.assertRedirects(
            reponse_cloture,
            reverse("rapports:gestion_dossiers"),
        )
        dossier.refresh_from_db()
        self.assertEqual(dossier.statut, DossierEtudes.Statut.DIPLOME)
        self.assertEqual(dossier.motif_cloture, "Diplome confirme par le jury")
        self.assertEqual(dossier.cree_par, self.personnel)
        self.assertTrue(
            JournalAction.objects.filter(
                action="dossier.modifie", identifiant_objet=str(dossier.pk)
            ).exists()
        )

    def test_personnel_ne_peut_pas_modifier_un_dossier_hors_entite(self):
        autre_entite = Entite.objects.create(
            code="fla-dossier",
            nom="Faculte de linguistique",
            regime=Entite.Regime.COHORTE,
        )
        autre_programme = Programme.objects.create(
            entite=autre_entite,
            code="linguistique",
            nom="Linguistique",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        autre_etudiant = self.creer_utilisateur(
            "etudiant-fla-dossier", Utilisateur.Role.ETUDIANT, autre_entite
        )
        dossier = DossierEtudes.objects.create(
            etudiant=autre_etudiant,
            programme=autre_programme,
            statut=DossierEtudes.Statut.EN_COURS,
            date_ouverture=date(2026, 9, 1),
            cree_par=self.personnel,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:modifier_dossier", args=(dossier.pk,))
        )

        self.assertEqual(reponse.status_code, 404)

    def test_liste_etudiants_filtre_et_imprime_par_programme_periode_statut(self):
        InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
        )
        autre_etudiant = self.creer_utilisateur(
            "etudiant-en-attente-liste", Utilisateur.Role.ETUDIANT, self.entite
        )
        InscriptionPedagogique.objects.create(
            etudiant=autre_etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.EN_ATTENTE,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:liste_etudiants"),
            {
                "periode": self.periode.pk,
                "programme": self.programme.pk,
                "statut": InscriptionPedagogique.Statut.VALIDEE,
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.etudiant.profil_etudiant.code_etudiant)
        self.assertNotContains(reponse, autre_etudiant.username)
        self.assertContains(reponse, "Imprimer la liste")

    def test_liste_etudiants_filtre_les_conditions_de_passage(self):
        self.periode.date_debut = date(2026, 9, 1)
        self.periode.save(update_fields=("date_debut",))
        RegleAcademique.objects.create(
            entite=self.entite,
            version="reglement-passage",
            date_effet=date(2026, 8, 1),
            parametres={
                "seuil_reussite_cours": "65",
                "seuil_reprise_cours": "50",
            },
        )
        cours = Cours.objects.create(
            programme=self.programme,
            code="BIO101",
            nom="Biologie generale",
        )
        inscription_reussie = InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
        )
        SelectionCours.objects.create(
            inscription=inscription_reussie,
            cours=cours,
        )
        etudiant_echec = self.creer_utilisateur(
            "etudiant-echec-passage", Utilisateur.Role.ETUDIANT, self.entite
        )
        ProfilEtudiant.objects.create(
            utilisateur=etudiant_echec,
            code_etudiant="FAMV-004",
            sexe=ProfilEtudiant.Sexe.MASCULIN,
        )
        inscription_echec = InscriptionPedagogique.objects.create(
            etudiant=etudiant_echec,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
        )
        SelectionCours.objects.create(inscription=inscription_echec, cours=cours)
        etudiant_en_attente = self.creer_utilisateur(
            "etudiant-notes-en-attente", Utilisateur.Role.ETUDIANT, self.entite
        )
        inscription_en_attente = InscriptionPedagogique.objects.create(
            etudiant=etudiant_en_attente,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
        )
        SelectionCours.objects.create(inscription=inscription_en_attente, cours=cours)
        for etudiant, note in ((self.etudiant, 75), (etudiant_echec, 40)):
            Evaluation.objects.create(
                cours=cours,
                periode=self.periode,
                etudiant=etudiant,
                libelle="Examen final",
                note=note,
                coefficient=1,
                est_publiee=True,
                saisie_par=self.personnel,
            )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:liste_etudiants"),
            {
                "periode": self.periode.pk,
                "programme": self.programme.pk,
                "statut_passage": "reussite",
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "FAMV-001")
        self.assertNotContains(reponse, "FAMV-004")
        self.assertContains(reponse, "Conditions de passage")

        reponse_en_attente = self.client.get(
            reverse("rapports:liste_etudiants"),
            {
                "periode": self.periode.pk,
                "programme": self.programme.pk,
                "statut_passage": "en_attente",
            },
        )

        self.assertEqual(reponse_en_attente.status_code, 200)
        self.assertContains(reponse_en_attente, "etudiant-notes-en-attente")
        self.assertNotContains(reponse_en_attente, "FAMV-004")

    def test_credits_suffisants_valident_le_passage_malgre_une_moyenne_basse(self):
        self.periode.date_debut = date(2026, 9, 1)
        self.periode.save(update_fields=("date_debut",))
        self.programme.credits_requis = 2
        self.programme.save(update_fields=("credits_requis",))
        RegleAcademique.objects.create(
            entite=self.entite,
            version="reglement-credits",
            date_effet=date(2026, 8, 1),
            parametres={
                "seuil_reussite_cours": "65",
                "seuil_reprise_cours": "50",
            },
        )
        cours_reussi = Cours.objects.create(
            programme=self.programme,
            code="BIO-CREDITS",
            nom="Cours acquis",
            credits=2,
        )
        cours_echoue = Cours.objects.create(
            programme=self.programme,
            code="MAT-CREDITS",
            nom="Cours non acquis",
            credits=10,
        )
        inscription = InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
        )
        for cours, note in ((cours_reussi, 100), (cours_echoue, 20)):
            SelectionCours.objects.create(inscription=inscription, cours=cours)
            Evaluation.objects.create(
                cours=cours,
                periode=self.periode,
                etudiant=self.etudiant,
                libelle="Examen final",
                note=note,
                coefficient=1,
                est_publiee=True,
                saisie_par=self.personnel,
            )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:liste_etudiants"),
            {
                "periode": self.periode.pk,
                "programme": self.programme.pk,
                "statut_passage": "reussite",
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.etudiant.profil_etudiant.code_etudiant)

    def test_frais_actifs_non_acquittes_bloquent_la_reussite(self):
        self.periode.date_debut = date(2026, 9, 1)
        self.periode.save(update_fields=("date_debut",))
        RegleAcademique.objects.create(
            entite=self.entite,
            version="reglement-paiement-passage",
            date_effet=date(2026, 8, 1),
            parametres={"seuil_reussite_cours": "65"},
        )
        cours = Cours.objects.create(
            programme=self.programme,
            code="BIO-PAIEMENT",
            nom="Cours avec tarif",
        )
        inscription = InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
        )
        SelectionCours.objects.create(inscription=inscription, cours=cours)
        Evaluation.objects.create(
            cours=cours,
            periode=self.periode,
            etudiant=self.etudiant,
            libelle="Examen final",
            note=80,
            coefficient=1,
            est_publiee=True,
            saisie_par=self.personnel,
        )
        tarif = TarifScolarite.objects.create(
            programme=self.programme,
            periode=self.periode,
            montant=Decimal("1000"),
        )
        self.client.force_login(self.personnel)
        filtres = {
            "periode": self.periode.pk,
            "programme": self.programme.pk,
            "statut_passage": "frais_non_acquittes",
        }

        reponse_non_paye = self.client.get(reverse("rapports:liste_etudiants"), filtres)

        self.assertEqual(reponse_non_paye.status_code, 200)
        self.assertContains(
            reponse_non_paye, self.etudiant.profil_etudiant.code_etudiant
        )
        PaiementScolarite.objects.create(
            etudiant=self.etudiant,
            tarif=tarif,
            montant=Decimal("1000"),
            reference="PAIEMENT-PASSAGE-VALIDE",
            date_paiement=date(2026, 9, 1),
            statut=PaiementScolarite.Statut.VALIDE,
            valide_par=self.personnel,
        )

        reponse_paye = self.client.get(
            reverse("rapports:liste_etudiants"),
            {**filtres, "statut_passage": "reussite"},
        )

        self.assertEqual(reponse_paye.status_code, 200)
        self.assertContains(reponse_paye, self.etudiant.profil_etudiant.code_etudiant)

    def test_liste_paiements_acquittes_inclut_etudiant_non_inscrit(self):
        tarif = TarifScolarite.objects.create(
            programme=self.programme,
            periode=self.periode,
            montant=Decimal("1000.00"),
        )
        PaiementScolarite.objects.create(
            etudiant=self.etudiant,
            tarif=tarif,
            montant=Decimal("1000.00"),
            reference="PAYE-COMPLET",
            date_paiement=date(2026, 9, 1),
            statut=PaiementScolarite.Statut.VALIDE,
            valide_par=self.personnel,
        )
        etudiant_partiel = self.creer_utilisateur(
            "etudiant-paiement-partiel", Utilisateur.Role.ETUDIANT, self.entite
        )
        PaiementScolarite.objects.create(
            etudiant=etudiant_partiel,
            tarif=tarif,
            montant=Decimal("500.00"),
            reference="PAYE-PARTIEL",
            date_paiement=date(2026, 9, 2),
            statut=PaiementScolarite.Statut.VALIDE,
            valide_par=self.personnel,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:liste_paiements_acquittes"),
            {"periode": self.periode.pk, "programme": self.programme.pk},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.etudiant.profil_etudiant.code_etudiant)
        self.assertNotContains(reponse, etudiant_partiel.username)
        self.assertContains(reponse, "Imprimer la liste")

    def test_liste_etudiants_peut_etre_filtree_par_niveau(self):
        periode_niveau = PeriodeAcademique.objects.create(
            entite=self.entite,
            code="niveau-1",
            nom="Niveau 1",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.NIVEAU,
        )
        inscription_niveau = InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=periode_niveau,
            statut=InscriptionPedagogique.Statut.VALIDEE,
        )
        etudiant_autre_niveau = self.creer_utilisateur(
            "etudiant-autre-niveau", Utilisateur.Role.ETUDIANT, self.entite
        )
        ProfilEtudiant.objects.create(
            utilisateur=etudiant_autre_niveau,
            code_etudiant="FAMV-002",
            sexe=ProfilEtudiant.Sexe.MASCULIN,
        )
        inscription_autre_niveau = InscriptionPedagogique.objects.create(
            etudiant=etudiant_autre_niveau,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:liste_etudiants"),
            {"niveau": periode_niveau.pk},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(
            reponse, inscription_niveau.etudiant.profil_etudiant.code_etudiant
        )
        self.assertContains(reponse, "Niveau 1")
        self.assertNotContains(reponse, inscription_autre_niveau.etudiant.username)
        self.assertContains(reponse, "Niveau")

    def test_liste_etudiants_filtre_par_statut_du_dossier(self):
        InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
        )
        DossierEtudes.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            statut=DossierEtudes.Statut.ABANDON,
            date_ouverture=date(2025, 9, 1),
            date_cloture=date(2026, 2, 1),
            motif_cloture="Abandon des etudes",
            cree_par=self.personnel,
        )
        autre_etudiant = self.creer_utilisateur(
            "etudiant-dossier-actif", Utilisateur.Role.ETUDIANT, self.entite
        )
        ProfilEtudiant.objects.create(
            utilisateur=autre_etudiant,
            code_etudiant="FAMV-002",
            sexe=ProfilEtudiant.Sexe.MASCULIN,
        )
        InscriptionPedagogique.objects.create(
            etudiant=autre_etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
        )
        DossierEtudes.objects.create(
            etudiant=autre_etudiant,
            programme=self.programme,
            statut=DossierEtudes.Statut.EN_COURS,
            date_ouverture=date(2026, 9, 1),
            cree_par=self.personnel,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:liste_etudiants"),
            {"statut_dossier": DossierEtudes.Statut.ABANDON},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.etudiant.profil_etudiant.code_etudiant)
        self.assertContains(reponse, "Abandon")
        self.assertNotContains(reponse, autre_etudiant.username)
        self.assertContains(reponse, "Statut du dossier")

    def test_diplome_exige_un_dossier_au_statut_diplome(self):
        acte = ActeAcademique(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            type_acte=ActeAcademique.TypeActe.DIPLOME,
            reference="DIP-TEST-001",
            date_delivrance=date(2026, 10, 1),
            delivre_par=self.personnel,
        )

        with self.assertRaisesMessage(
            ValidationError, "dossier d'etudes au statut diplome"
        ):
            acte.full_clean()

        DossierEtudes.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            statut=DossierEtudes.Statut.DIPLOME,
            date_ouverture=date(2022, 9, 1),
            date_cloture=date(2026, 9, 1),
            cree_par=self.personnel,
        )
        acte.full_clean()
