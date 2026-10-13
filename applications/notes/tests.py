import unittest
from io import BytesIO
from decimal import Decimal
from datetime import date, datetime
from types import SimpleNamespace

from openpyxl import Workbook

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from applications.audit.models import JournalAction
from applications.comptes.models import ProfilEtudiant, Utilisateur
from applications.inscriptions.models import (
    InscriptionPedagogique,
    SelectionCours,
)
from applications.notes.models import Evaluation, ProgrammationExamen
from applications.referentiels.models import (
    AffectationCours,
    Cours,
    Entite,
    PeriodeAcademique,
    Programme,
    RegleAcademique,
)

from applications.notes.services.famv_2016 import (
    TypeDecision,
    evaluer_passage_famv_2016,
)
from applications.notes.services.resultats import calculer_moyenne_ponderee


class ReglesPassageFAMV2016Tests(unittest.TestCase):
    def test_admission_a_65_meme_avec_plusieurs_notes_sous_40(self):
        decision = evaluer_passage_famv_2016(
            2, "65", {"BIO101": "39", "MAT101": "35", "CHM101": "80"}
        )

        self.assertEqual(decision.type_decision, TypeDecision.ADMIS)

    def test_reprise_de_tous_les_cours_sous_65_entre_60_et_65(self):
        decision = evaluer_passage_famv_2016(
            3, "60", {"BIO201": "61", "MAT201": "49", "CHM201": "65"}
        )

        self.assertEqual(decision.type_decision, TypeDecision.REPRISE)
        self.assertEqual(decision.cours_a_reprendre, ("BIO201", "MAT201"))

    def test_moyenne_sous_60_est_un_echec_apres_la_premiere_annee(self):
        decision = evaluer_passage_famv_2016(2, "59.99", {"BIO101": "60"})

        self.assertEqual(decision.type_decision, TypeDecision.ECHEC)

    def test_moyenne_sous_60_est_un_echec_en_premiere_annee(self):
        decision = evaluer_passage_famv_2016(1, "59.99", {"BIO101": "60"})

        self.assertEqual(decision.type_decision, TypeDecision.ECHEC)

    def test_les_seuils_sont_inclusifs_a_60_et_65(self):
        reprise = evaluer_passage_famv_2016(2, "60", {"BIO101": "60"})
        admission = evaluer_passage_famv_2016(2, "65", {"BIO101": "65"})

        self.assertEqual(reprise.type_decision, TypeDecision.REPRISE)
        self.assertEqual(admission.type_decision, TypeDecision.ADMIS)

    def test_convertit_la_moyenne_en_decimal(self):
        decision = evaluer_passage_famv_2016(2, 65, {"BIO101": 65})

        self.assertEqual(decision.moyenne_annuelle, Decimal("65"))

    def test_refuse_une_annee_invalide(self):
        with self.assertRaises(ValueError):
            evaluer_passage_famv_2016(6, "65", {"BIO101": "65"})

    def test_refuse_une_note_hors_limites(self):
        with self.assertRaises(ValueError):
            evaluer_passage_famv_2016(2, "65", {"BIO101": "100.01"})


class MoyennePondereeTests(unittest.TestCase):
    def test_calcule_et_arrondit_une_moyenne_ponderee(self):
        evaluations = [
            SimpleNamespace(note=Decimal("80"), coefficient=Decimal("2")),
            SimpleNamespace(note=Decimal("60"), coefficient=Decimal("1")),
        ]

        moyenne = calculer_moyenne_ponderee(evaluations)

        self.assertEqual(moyenne, Decimal("73.33"))

    def test_retourne_aucun_resultat_sans_evaluation(self):
        self.assertIsNone(calculer_moyenne_ponderee([]))

    def test_refuse_un_coefficient_non_positif(self):
        evaluations = [SimpleNamespace(note=Decimal("80"), coefficient=Decimal("0"))]

        with self.assertRaises(ValueError):
            calculer_moyenne_ponderee(evaluations)


class ProgrammationExamensTests(TestCase):
    def setUp(self):
        self.entite = Entite.objects.create(
            code="examens-famv",
            nom="Faculte des examens",
            regime=Entite.Regime.COHORTE,
        )
        self.programme = Programme.objects.create(
            entite=self.entite,
            code="programme-examens",
            nom="Programme examens",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        self.periode = PeriodeAcademique.objects.create(
            entite=self.entite,
            code="2026-examens",
            nom="Session examens",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
        )
        self.cours = Cours.objects.create(
            programme=self.programme,
            code="EXA101",
            nom="Cours avec examen",
        )
        self.autre_cours = Cours.objects.create(
            programme=self.programme,
            code="EXA102",
            nom="Autre cours",
        )
        self.personnel = self.creer_utilisateur(
            "personnel-examens", Utilisateur.Role.PERSONNEL
        )
        self.professeur = self.creer_utilisateur(
            "professeur-examens", Utilisateur.Role.PROFESSEUR
        )
        self.etudiant = self.creer_utilisateur(
            "etudiant-examens", Utilisateur.Role.ETUDIANT
        )
        AffectationCours.objects.create(
            professeur=self.professeur,
            cours=self.cours,
            periode=self.periode,
        )
        inscription = InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
        )
        SelectionCours.objects.create(inscription=inscription, cours=self.cours)

    def creer_utilisateur(self, username, role):
        return Utilisateur.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="mot-de-passe-de-test",
            role=role,
            entite=self.entite,
        )

    def creer_examen(self, cours, libelle, salle, heure_debut=9):
        examen = ProgrammationExamen(
            cours=cours,
            periode=self.periode,
            libelle=libelle,
            date_debut=timezone.make_aware(datetime(2026, 10, 20, heure_debut)),
            date_fin=timezone.make_aware(datetime(2026, 10, 20, heure_debut + 2)),
            salle=salle,
            planifie_par=self.personnel,
        )
        examen.full_clean()
        examen.save()
        return examen

    def test_registrariat_programme_un_examen_et_l_action_est_journalisee(self):
        self.client.force_login(self.personnel)

        reponse = self.client.post(
            reverse("notes:gestion_examens"),
            {
                "cours": self.cours.pk,
                "periode": self.periode.pk,
                "libelle": "Examen final",
                "date_debut": "2026-10-20T09:00",
                "date_fin": "2026-10-20T11:00",
                "salle": "Salle A",
                "consignes": "Apporter une piece d'identite.",
                "statut": ProgrammationExamen.Statut.PLANIFIE,
            },
        )

        self.assertRedirects(reponse, reverse("notes:gestion_examens"))
        examen = ProgrammationExamen.objects.get(libelle="Examen final")
        self.assertEqual(examen.planifie_par, self.personnel)
        self.assertTrue(
            JournalAction.objects.filter(
                utilisateur=self.personnel,
                action="examen.planifie",
                identifiant_objet=str(examen.pk),
            ).exists()
        )

    def test_calendrier_est_limite_aux_affectations_et_cours_selectionnes(self):
        examen_visible = self.creer_examen(self.cours, "Examen visible", "Salle A")
        self.creer_examen(self.autre_cours, "Examen prive", "Salle B", 13)

        self.client.force_login(self.professeur)
        calendrier_professeur = self.client.get(reverse("notes:calendrier_examens"))
        self.assertContains(calendrier_professeur, examen_visible.libelle)
        self.assertNotContains(calendrier_professeur, "Examen prive")

        self.client.force_login(self.etudiant)
        calendrier_etudiant = self.client.get(reverse("notes:calendrier_examens"))
        self.assertContains(calendrier_etudiant, examen_visible.libelle)
        self.assertNotContains(calendrier_etudiant, "Examen prive")

    def test_seuls_le_registrariat_et_le_superutilisateur_peuvent_modifier(self):
        self.client.force_login(self.professeur)
        reponse_professeur = self.client.get(reverse("notes:gestion_examens"))
        self.assertEqual(reponse_professeur.status_code, 403)

        self.client.force_login(self.etudiant)
        reponse_etudiant = self.client.get(reverse("notes:gestion_examens"))
        self.assertEqual(reponse_etudiant.status_code, 403)

    def test_refuse_un_examen_qui_chevauche_la_meme_salle(self):
        self.creer_examen(self.cours, "Premier examen", "Salle A")
        autre_examen = ProgrammationExamen(
            cours=self.autre_cours,
            periode=self.periode,
            libelle="Deuxieme examen",
            date_debut=timezone.make_aware(datetime(2026, 10, 20, 10)),
            date_fin=timezone.make_aware(datetime(2026, 10, 20, 12)),
            salle="Salle A",
            planifie_par=self.personnel,
        )

        with self.assertRaises(ValidationError):
            autre_examen.full_clean()


class FluxNotesTests(TestCase):
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
        self.cours = Cours.objects.create(
            programme=self.programme,
            code="AGR101",
            nom="Agronomie generale",
        )
        self.professeur = self.creer_utilisateur(
            "prof-notes", Utilisateur.Role.PROFESSEUR
        )
        self.personnel = self.creer_utilisateur(
            "registrariat-notes", Utilisateur.Role.PERSONNEL
        )
        self.etudiant = self.creer_utilisateur(
            "etudiant-notes", Utilisateur.Role.ETUDIANT
        )
        self.code_etudiant = "FAMV-NOTES-001"
        ProfilEtudiant.objects.create(
            utilisateur=self.etudiant,
            code_etudiant=self.code_etudiant,
        )
        AffectationCours.objects.create(
            professeur=self.professeur,
            cours=self.cours,
            periode=self.periode,
        )
        inscription = InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
            traite_par=self.personnel,
        )
        SelectionCours.objects.create(inscription=inscription, cours=self.cours)

    def creer_utilisateur(self, nom, role):
        return Utilisateur.objects.create_user(
            username=nom,
            email=f"{nom}@example.test",
            password="mot-de-passe-de-test",
            role=role,
            entite=self.entite,
        )

    def creer_fichier_excel(self, lignes):
        classeur = Workbook()
        feuille = classeur.active
        feuille.append(("code_etudiant", "evaluation", "note", "coefficient"))
        for ligne in lignes:
            feuille.append(ligne)
        contenu = BytesIO()
        classeur.save(contenu)
        return SimpleUploadedFile(
            "notes.xlsx",
            contenu.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_importe_les_notes_excel_et_journalise_loperation(self):
        self.client.force_login(self.professeur)

        reponse = self.client.post(
            reverse(
                "notes:importer_evaluations_excel",
                args=(self.cours.pk, self.periode.pk),
            ),
            {
                "fichier": self.creer_fichier_excel(
                    [(self.code_etudiant, "Examen final", 82.5, 2)]
                )
            },
        )

        self.assertRedirects(
            reponse,
            reverse("notes:saisir_evaluation", args=(self.cours.pk, self.periode.pk)),
        )
        evaluation = Evaluation.objects.get(etudiant=self.etudiant, cours=self.cours)
        self.assertEqual(evaluation.note, Decimal("82.5"))
        self.assertEqual(evaluation.coefficient, Decimal("2"))
        self.assertEqual(evaluation.saisie_par, self.professeur)
        self.assertTrue(
            JournalAction.objects.filter(
                utilisateur=self.professeur,
                action="notes.importees",
                details__nombre=1,
            ).exists()
        )

    def test_import_excel_invalide_nenregistre_aucune_ligne(self):
        self.client.force_login(self.professeur)

        reponse = self.client.post(
            reverse(
                "notes:importer_evaluations_excel",
                args=(self.cours.pk, self.periode.pk),
            ),
            {
                "fichier": self.creer_fichier_excel(
                    [
                        (self.code_etudiant, "Examen final", 82, 1),
                        ("code-inconnu", "Examen final", 70, 1),
                    ]
                )
            },
            follow=True,
        )

        self.assertContains(reponse, "code etudiant inconnu")
        self.assertFalse(Evaluation.objects.filter(cours=self.cours).exists())
        self.assertFalse(
            JournalAction.objects.filter(action="notes.importees").exists()
        )

    def test_import_excel_ne_modifie_pas_une_note_deja_publiee(self):
        evaluation = Evaluation.objects.create(
            cours=self.cours,
            periode=self.periode,
            etudiant=self.etudiant,
            libelle="Examen final",
            note=Decimal("75"),
            coefficient=Decimal("1"),
            est_publiee=True,
            saisie_par=self.professeur,
        )
        self.client.force_login(self.professeur)

        reponse = self.client.post(
            reverse(
                "notes:importer_evaluations_excel",
                args=(self.cours.pk, self.periode.pk),
            ),
            {
                "fichier": self.creer_fichier_excel(
                    [(self.code_etudiant, "Examen final", 90, 1)]
                )
            },
            follow=True,
        )

        self.assertContains(reponse, "note publiee")
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.note, Decimal("75"))

    def test_professeur_saisit_une_note_pour_un_etudiant_inscrit(self):
        self.client.force_login(self.professeur)

        reponse = self.client.post(
            reverse(
                "notes:saisir_evaluation",
                args=(self.cours.pk, self.periode.pk),
            ),
            {
                "etudiant": self.etudiant.pk,
                "libelle": "Examen final",
                "note": "82.50",
                "coefficient": "2.00",
            },
        )

        self.assertRedirects(
            reponse,
            reverse("notes:saisir_evaluation", args=(self.cours.pk, self.periode.pk)),
        )
        evaluation = self.etudiant.evaluations.get(cours=self.cours)
        self.assertEqual(evaluation.note, Decimal("82.50"))
        self.assertFalse(evaluation.est_publiee)
        self.assertTrue(
            JournalAction.objects.filter(
                action="note.saisiee", identifiant_objet=str(evaluation.pk)
            ).exists()
        )

    def test_professeur_ne_peut_pas_saisir_pour_un_non_inscrit(self):
        autre_etudiant = self.creer_utilisateur(
            "etudiant-non-inscrit", Utilisateur.Role.ETUDIANT
        )
        self.client.force_login(self.professeur)

        reponse = self.client.post(
            reverse(
                "notes:saisir_evaluation",
                args=(self.cours.pk, self.periode.pk),
            ),
            {
                "etudiant": autre_etudiant.pk,
                "libelle": "Examen final",
                "note": "82.50",
                "coefficient": "1.00",
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Evaluation.objects.filter(etudiant=autre_etudiant).exists())

    def test_un_professeur_non_affecte_ne_peut_pas_saisir(self):
        autre_professeur = self.creer_utilisateur(
            "autre-prof-notes", Utilisateur.Role.PROFESSEUR
        )
        self.client.force_login(autre_professeur)

        reponse = self.client.get(
            reverse(
                "notes:saisir_evaluation",
                args=(self.cours.pk, self.periode.pk),
            )
        )

        self.assertEqual(reponse.status_code, 404)

    def test_etudiant_ne_voit_une_note_quapres_publication(self):
        evaluation = Evaluation.objects.create(
            cours=self.cours,
            periode=self.periode,
            etudiant=self.etudiant,
            libelle="Examen final",
            note=Decimal("75.00"),
            coefficient=Decimal("1.00"),
            saisie_par=self.professeur,
        )
        self.client.force_login(self.etudiant)
        url_resultats = reverse("notes:resultats_etudiant")

        reponse_confidentielle = self.client.get(url_resultats)

        self.assertEqual(reponse_confidentielle.status_code, 200)
        self.assertNotContains(reponse_confidentielle, "Examen final")
        self.client.force_login(self.personnel)
        reponse_publication = self.client.post(
            reverse(
                "notes:publier_notes_cours",
                args=(self.cours.pk, self.periode.pk),
            )
        )

        self.assertRedirects(reponse_publication, reverse("notes:notes_a_publier"))
        evaluation.refresh_from_db()
        self.assertTrue(evaluation.est_publiee)
        self.client.force_login(self.etudiant)
        reponse_publiee = self.client.get(url_resultats)
        self.assertContains(reponse_publiee, "Examen final")
        self.assertContains(reponse_publiee, "75")

    def test_etudiant_consulte_et_imprime_les_notes_de_la_periode_precedente(self):
        self.periode.date_debut = date(2026, 9, 1)
        self.periode.save(update_fields=("date_debut",))
        periode_reference = PeriodeAcademique.objects.create(
            entite=self.entite,
            code="2027-s2",
            nom="Deuxieme session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
            date_debut=date(2027, 1, 10),
        )
        inscription_reference = InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=periode_reference,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
            traite_par=self.personnel,
        )
        SelectionCours.objects.create(
            inscription=inscription_reference,
            cours=self.cours,
        )
        Evaluation.objects.create(
            cours=self.cours,
            periode=self.periode,
            etudiant=self.etudiant,
            libelle="Examen session precedente",
            note=Decimal("78"),
            coefficient=Decimal("1"),
            est_publiee=True,
            saisie_par=self.professeur,
        )
        self.client.force_login(self.etudiant)

        reponse = self.client.get(
            reverse("notes:resultats_etudiant"),
            {
                "programme": self.programme.pk,
                "periode_reference": periode_reference.pk,
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Premiere session")
        self.assertContains(reponse, "Examen session precedente")
        self.assertNotContains(reponse, "Imprimer le releve")

    def test_page_releves_registrariat_ne_signale_pas_d_erreur_sans_filtre(self):
        self.client.force_login(self.personnel)

        reponse = self.client.get(reverse("notes:releves_etudiants"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Choisir la periode de reference")
        self.assertNotContains(reponse, "__all__")
        self.assertNotContains(reponse, "Choisissez un programme")

    def test_registrariat_filtre_liste_notes_et_moyennes_par_perimetre(self):
        self.periode.date_debut = date(2026, 9, 1)
        self.periode.save(update_fields=("date_debut",))
        RegleAcademique.objects.create(
            entite=self.entite,
            version="regle-mentions-liste-notes",
            date_effet=date(2026, 8, 1),
            parametres={
                "seuil_reussite_cours": "65",
                "seuil_reprise_cours": "60",
                "mentions": {"Passable": 60, "Bien": 70, "Tres bien": 85},
            },
        )
        autre_cours = Cours.objects.create(
            programme=self.programme,
            code="AGR102",
            nom="Economie rurale",
            credits=3,
        )
        self.cours.credits = 2
        self.cours.save(update_fields=("credits",))
        for cours, libelle, note in (
            (self.cours, "Examen botanique", 70),
            (autre_cours, "Examen economie", 90),
        ):
            Evaluation.objects.create(
                cours=cours,
                periode=self.periode,
                etudiant=self.etudiant,
                libelle=libelle,
                note=Decimal(str(note)),
                coefficient=Decimal("1"),
                est_publiee=True,
                saisie_par=self.professeur,
            )
        Evaluation.objects.create(
            cours=self.cours,
            periode=self.periode,
            etudiant=self.etudiant,
            libelle="Evaluation en attente",
            note=Decimal("10"),
            coefficient=Decimal("1"),
            est_publiee=False,
            saisie_par=self.professeur,
        )
        autre_periode = PeriodeAcademique.objects.create(
            entite=self.entite,
            code="2026-s2-notes",
            nom="Deuxieme session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
        )
        Evaluation.objects.create(
            cours=self.cours,
            periode=autre_periode,
            etudiant=self.etudiant,
            libelle="Note hors periode",
            note=Decimal("10"),
            coefficient=Decimal("1"),
            est_publiee=True,
            saisie_par=self.professeur,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("notes:liste_evaluations"),
            {
                "programme": self.programme.pk,
                "periode": self.periode.pk,
                "cours": [self.cours.pk, autre_cours.pk],
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Examen botanique")
        self.assertContains(reponse, "Examen economie")
        self.assertContains(reponse, "Evaluation en attente")
        self.assertNotContains(reponse, "Note hors periode")
        self.assertContains(reponse, "FAMV-NOTES-001")
        self.assertContains(reponse, "Moyenne par programme")
        self.assertContains(reponse, "Bien")
        self.assertEqual(
            reponse.context["moyennes"]["programmes"][0]["moyenne"],
            Decimal("82.00"),
        )

    def test_etudiant_ne_peut_pas_consulter_la_liste_generale_des_notes(self):
        self.client.force_login(self.etudiant)

        reponse = self.client.get(reverse("notes:liste_evaluations"))

        self.assertEqual(reponse.status_code, 403)

    def test_note_eliminatoire_fait_echouer_les_conditions_de_passage(self):
        self.periode.date_debut = date(2026, 9, 1)
        self.periode.save(update_fields=("date_debut",))
        RegleAcademique.objects.create(
            entite=self.entite,
            version="regle-eliminatoire-notes",
            date_effet=date(2026, 8, 1),
            parametres={
                "seuil_reussite_cours": "65",
                "seuil_reprise_cours": "60",
                "note_eliminatoire": "40",
            },
        )
        for libelle, note in (("Devoir", 90), ("Examen eliminatoire", 39)):
            Evaluation.objects.create(
                cours=self.cours,
                periode=self.periode,
                etudiant=self.etudiant,
                libelle=libelle,
                note=Decimal(str(note)),
                coefficient=Decimal("1"),
                est_publiee=True,
                saisie_par=self.professeur,
            )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("rapports:liste_etudiants"),
            {
                "periode": self.periode.pk,
                "programme": self.programme.pk,
                "statut_passage": "echec",
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.code_etudiant)

    def test_registrariat_peut_imprimer_le_releve_precedent_d_un_etudiant(self):
        self.periode.date_debut = date(2026, 9, 1)
        self.periode.save(update_fields=("date_debut",))
        periode_reference = PeriodeAcademique.objects.create(
            entite=self.entite,
            code="2027-s2-registrariat",
            nom="Deuxieme session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
            date_debut=date(2027, 1, 10),
        )
        inscription_reference = InscriptionPedagogique.objects.create(
            etudiant=self.etudiant,
            programme=self.programme,
            periode=periode_reference,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
            traite_par=self.personnel,
        )
        SelectionCours.objects.create(
            inscription=inscription_reference,
            cours=self.cours,
        )
        Evaluation.objects.create(
            cours=self.cours,
            periode=self.periode,
            etudiant=self.etudiant,
            libelle="Examen precedent",
            note=Decimal("78"),
            coefficient=Decimal("1"),
            est_publiee=True,
            saisie_par=self.professeur,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("notes:releves_etudiants"),
            {
                "etudiant": self.etudiant.pk,
                "programme": self.programme.pk,
                "periode_reference": periode_reference.pk,
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Examen precedent")
        self.assertContains(reponse, "Imprimer le releve")

    def test_registrariat_consulte_les_notes_precedentes_d_un_programme(self):
        self.periode.date_debut = date(2026, 9, 1)
        self.periode.save(update_fields=("date_debut",))
        periode_reference = PeriodeAcademique.objects.create(
            entite=self.entite,
            code="2027-s2-programme",
            nom="Deuxieme session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
            date_debut=date(2027, 1, 10),
        )
        for etudiant in (self.etudiant,):
            inscription_reference = InscriptionPedagogique.objects.create(
                etudiant=etudiant,
                programme=self.programme,
                periode=periode_reference,
                statut=InscriptionPedagogique.Statut.VALIDEE,
                conditions_passage_verifiees=True,
                traite_par=self.personnel,
            )
            SelectionCours.objects.create(
                inscription=inscription_reference,
                cours=self.cours,
            )
        autre_etudiant = self.creer_utilisateur(
            "etudiant-releve-programme", Utilisateur.Role.ETUDIANT
        )
        inscription_precedente = InscriptionPedagogique.objects.create(
            etudiant=autre_etudiant,
            programme=self.programme,
            periode=self.periode,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
            traite_par=self.personnel,
        )
        SelectionCours.objects.create(
            inscription=inscription_precedente,
            cours=self.cours,
        )
        inscription_reference_autre = InscriptionPedagogique.objects.create(
            etudiant=autre_etudiant,
            programme=self.programme,
            periode=periode_reference,
            statut=InscriptionPedagogique.Statut.VALIDEE,
            conditions_passage_verifiees=True,
            traite_par=self.personnel,
        )
        SelectionCours.objects.create(
            inscription=inscription_reference_autre,
            cours=self.cours,
        )
        for etudiant, libelle, note in (
            (self.etudiant, "Examen programme 1", 78),
            (autre_etudiant, "Examen programme 2", 82),
        ):
            Evaluation.objects.create(
                cours=self.cours,
                periode=self.periode,
                etudiant=etudiant,
                libelle=libelle,
                note=Decimal(str(note)),
                coefficient=Decimal("1"),
                est_publiee=True,
                saisie_par=self.professeur,
            )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("notes:releves_etudiants"),
            {
                "programme": self.programme.pk,
                "periode_reference": periode_reference.pk,
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Examen programme 1")
        self.assertContains(reponse, "Examen programme 2")
        self.assertContains(reponse, "etudiant-releve-programme")

    def test_registrariat_retire_une_publication_et_professeur_corrige_la_note(self):
        evaluation = Evaluation.objects.create(
            cours=self.cours,
            periode=self.periode,
            etudiant=self.etudiant,
            libelle="Examen final",
            note=Decimal("75.00"),
            coefficient=Decimal("1.00"),
            est_publiee=True,
            saisie_par=self.professeur,
        )
        autre_evaluation = Evaluation.objects.create(
            cours=self.cours,
            periode=self.periode,
            etudiant=self.etudiant,
            libelle="Devoir",
            note=Decimal("80.00"),
            coefficient=Decimal("1.00"),
            est_publiee=True,
            saisie_par=self.professeur,
        )
        self.client.force_login(self.personnel)

        page_publication = self.client.get(reverse("notes:notes_a_publier"))
        self.assertContains(page_publication, "Notes publiees")
        self.assertContains(page_publication, "Retirer la publication")
        self.assertContains(
            page_publication,
            reverse("notes:retirer_publication_note", args=(evaluation.pk,)),
        )

        reponse_retrait = self.client.post(
            reverse("notes:retirer_publication_note", args=(evaluation.pk,))
        )

        self.assertRedirects(reponse_retrait, reverse("notes:notes_a_publier"))
        evaluation.refresh_from_db()
        autre_evaluation.refresh_from_db()
        self.assertFalse(evaluation.est_publiee)
        self.assertTrue(autre_evaluation.est_publiee)
        self.assertTrue(
            JournalAction.objects.filter(
                utilisateur=self.personnel,
                action="note.publication_retiree",
                identifiant_objet=str(evaluation.pk),
            ).exists()
        )

        self.client.force_login(self.etudiant)
        resultats = self.client.get(reverse("notes:resultats_etudiant"))
        self.assertNotContains(resultats, "Examen final")
        self.assertContains(resultats, "Devoir")

        self.client.force_login(self.professeur)
        correction = self.client.post(
            reverse(
                "notes:saisir_evaluation",
                args=(self.cours.pk, self.periode.pk),
            ),
            {
                "etudiant": self.etudiant.pk,
                "libelle": "Examen final",
                "note": "88.00",
                "coefficient": "1.00",
            },
        )

        self.assertRedirects(
            correction,
            reverse("notes:saisir_evaluation", args=(self.cours.pk, self.periode.pk)),
        )
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.note, Decimal("88.00"))
        self.assertFalse(evaluation.est_publiee)

    def test_personnel_ne_peut_pas_retirer_la_publication_hors_entite(self):
        autre_entite = Entite.objects.create(
            code="fla-depublication",
            nom="Faculte hors entite",
            regime=Entite.Regime.COHORTE,
        )
        autre_programme = Programme.objects.create(
            entite=autre_entite,
            code="autre-programme-depublication",
            nom="Autre programme",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        autre_cours = Cours.objects.create(
            programme=autre_programme,
            code="AUT101",
            nom="Cours hors entite",
        )
        autre_periode = PeriodeAcademique.objects.create(
            entite=autre_entite,
            code="2026-autre-depublication",
            nom="Autre periode",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
        )
        evaluation = Evaluation.objects.create(
            cours=autre_cours,
            periode=autre_periode,
            etudiant=self.etudiant,
            libelle="Examen",
            note=Decimal("75"),
            coefficient=Decimal("1"),
            est_publiee=True,
            saisie_par=self.professeur,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.post(
            reverse("notes:retirer_publication_note", args=(evaluation.pk,))
        )

        self.assertEqual(reponse.status_code, 404)
        evaluation.refresh_from_db()
        self.assertTrue(evaluation.est_publiee)

    def test_le_personnel_ne_peut_publier_que_dans_son_entite(self):
        autre_entite = Entite.objects.create(
            code="fla", nom="Faculte de linguistique", regime=Entite.Regime.COHORTE
        )
        autre_programme = Programme.objects.create(
            entite=autre_entite,
            code="linguistique",
            nom="Linguistique",
            type_programme=Programme.TypeProgramme.FORMATION,
        )
        autre_cours = Cours.objects.create(
            programme=autre_programme,
            code="LIN101",
            nom="Introduction a la linguistique",
        )
        autre_periode = PeriodeAcademique.objects.create(
            entite=autre_entite,
            code="2026-s1",
            nom="Premiere session",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.SESSION,
        )
        autre_etudiant = self.creer_utilisateur(
            "autre-etudiant", Utilisateur.Role.ETUDIANT
        )
        autre_evaluation = Evaluation.objects.create(
            cours=autre_cours,
            periode=autre_periode,
            etudiant=autre_etudiant,
            libelle="Examen",
            note=Decimal("80.00"),
            coefficient=Decimal("1.00"),
            saisie_par=self.personnel,
        )
        self.client.force_login(self.personnel)

        reponse = self.client.post(
            reverse(
                "notes:publier_notes_cours",
                args=(autre_cours.pk, autre_periode.pk),
            )
        )

        self.assertRedirects(reponse, reverse("notes:notes_a_publier"))
        autre_evaluation.refresh_from_db()
        self.assertFalse(autre_evaluation.est_publiee)
