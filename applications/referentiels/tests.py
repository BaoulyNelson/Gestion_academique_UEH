from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from applications.audit.models import JournalAction
from applications.comptes.models import Utilisateur
from applications.referentiels.forms import FormulaireRegleAcademique
from applications.referentiels.models import (
    Entite,
    PeriodeAcademique,
    RegleAcademique,
)


class GestionReglesAcademiquesTests(TestCase):
    def setUp(self):
        self.entite = Entite.objects.create(
            code="regles-tests",
            nom="Entite des regles",
            regime=Entite.Regime.COHORTE,
        )
        self.autre_entite = Entite.objects.create(
            code="autre-regles-tests",
            nom="Autre entite",
            regime=Entite.Regime.CREDITS,
        )
        self.personnel = Utilisateur.objects.create_user(
            username="registrariat-regles",
            email="registrariat-regles@example.test",
            password="mot-de-passe-de-test",
            role=Utilisateur.Role.PERSONNEL,
            entite=self.entite,
        )
        self.etudiant = Utilisateur.objects.create_user(
            username="etudiant-regles",
            email="etudiant-regles@example.test",
            password="mot-de-passe-de-test",
            role=Utilisateur.Role.ETUDIANT,
            entite=self.entite,
        )

    def donnees_regle(self, **remplacements):
        donnees = {
            "entite": self.entite.pk,
            "version": "reglement-2026",
            "date_effet": "2026-09-01",
            "est_active": "on",
            "seuil_reussite_cours": "65",
            "seuil_reprise_cours": "60",
            "note_eliminatoire": "35",
            "credits_requis": "30",
            "mentions": '{"Passable": 60, "Bien": 70}',
        }
        donnees.update(remplacements)
        return donnees

    def test_registrariat_enregistre_et_journalise_les_constantes(self):
        self.client.force_login(self.personnel)

        reponse = self.client.post(
            reverse("referentiels:regles_academiques"), self.donnees_regle()
        )

        self.assertRedirects(reponse, reverse("referentiels:regles_academiques"))
        regle = RegleAcademique.objects.get(entite=self.entite)
        self.assertEqual(
            Decimal(regle.parametres["seuil_reussite_cours"]), Decimal("65")
        )
        self.assertEqual(
            Decimal(regle.parametres["seuil_reprise_cours"]), Decimal("60")
        )
        self.assertEqual(Decimal(regle.parametres["note_eliminatoire"]), Decimal("35"))
        self.assertEqual(regle.parametres["credits_requis"], 30)
        self.assertEqual(regle.parametres["mentions"]["Bien"], 70)
        self.assertTrue(
            JournalAction.objects.filter(
                utilisateur=self.personnel,
                action="regle_academique.creee",
                identifiant_objet=str(regle.pk),
            ).exists()
        )

    def test_modification_preserve_les_parametres_json_non_edites(self):
        regle = RegleAcademique.objects.create(
            entite=self.entite,
            version="version-ancienne",
            date_effet=date(2025, 9, 1),
            parametres={"seuil_reussite_cours": "55", "cle_metier": "conservee"},
        )
        self.client.force_login(self.personnel)

        reponse = self.client.post(
            reverse("referentiels:modifier_regle_academique", args=(regle.pk,)),
            self.donnees_regle(version="version-ancienne", mentions=""),
        )

        self.assertRedirects(reponse, reverse("referentiels:regles_academiques"))
        regle.refresh_from_db()
        self.assertEqual(regle.parametres["cle_metier"], "conservee")
        self.assertEqual(
            Decimal(regle.parametres["seuil_reussite_cours"]), Decimal("65")
        )
        self.assertNotIn("mentions", regle.parametres)

    def test_refuse_une_reprise_superieure_au_seuil_de_reussite(self):
        formulaire = FormulaireRegleAcademique(
            self.donnees_regle(seuil_reprise_cours="70"),
            utilisateur=self.personnel,
        )

        self.assertFalse(formulaire.is_valid())
        self.assertIn("seuil_reprise_cours", formulaire.errors)

    def test_refuse_une_mention_hors_limites(self):
        formulaire = FormulaireRegleAcademique(
            self.donnees_regle(mentions='{"Distinction": 101}'),
            utilisateur=self.personnel,
        )

        self.assertFalse(formulaire.is_valid())
        self.assertIn("mentions", formulaire.errors)

    def test_etudiant_ne_peut_pas_gerer_les_constantes(self):
        self.client.force_login(self.etudiant)

        reponse = self.client.get(reverse("referentiels:regles_academiques"))

        self.assertEqual(reponse.status_code, 403)

    def test_personnel_ne_peut_pas_modifier_les_regles_d_une_autre_entite(self):
        regle = RegleAcademique.objects.create(
            entite=self.autre_entite,
            version="autre-version",
            date_effet=date(2026, 1, 1),
            parametres={},
        )
        self.client.force_login(self.personnel)

        reponse = self.client.get(
            reverse("referentiels:modifier_regle_academique", args=(regle.pk,))
        )

        self.assertEqual(reponse.status_code, 404)


class PeriodesAcademiquesTests(TestCase):
    def test_le_trimestre_est_un_type_de_periode_valide(self):
        entite = Entite.objects.create(
            code="trimestres-tests",
            nom="Entite des trimestres",
            regime=Entite.Regime.COHORTE,
        )

        periode = PeriodeAcademique.objects.create(
            entite=entite,
            code="2026-t1",
            nom="Premier trimestre",
            annee_academique="2026-2027",
            type_periode=PeriodeAcademique.TypePeriode.TRIMESTRE,
        )

        self.assertEqual(periode.get_type_periode_display(), "Trimestre")
