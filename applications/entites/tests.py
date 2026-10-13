from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from applications.entites.models import Entite, HoraireEntite


class ImportEntitesCsvTests(TestCase):
    def setUp(self):
        self.repertoire = TemporaryDirectory()
        self.addCleanup(self.repertoire.cleanup)
        self.fichier = Path(self.repertoire.name) / "entites.csv"

    def test_import_et_reimport_sont_idempotents_et_preservent_les_etats(self):
        self.fichier.write_text(
            "code,nom,email\nFDS,Faculté des Sciences,fds@example.ht\n",
            encoding="utf-8",
        )
        call_command("importer_entites", fichier=str(self.fichier), verbosity=0)
        entite = Entite.objects.get(code="FDS")
        self.assertEqual(entite.nom, "Faculté des Sciences")
        self.assertEqual(entite.email_contact, "fds@example.ht")
        self.assertTrue(entite.active)
        self.assertTrue(entite.inscription_ouverte)

        entite.active = False
        entite.inscription_ouverte = False
        entite.save(update_fields=["active", "inscription_ouverte"])
        call_command("importer_entites", fichier=str(self.fichier), verbosity=0)
        entite.refresh_from_db()
        self.assertFalse(entite.active)
        self.assertFalse(entite.inscription_ouverte)
        self.assertEqual(Entite.objects.filter(code="FDS").count(), 1)

    def test_csv_invalide_est_refuse_sans_import_partiel(self):
        self.fichier.write_text(
            "code,nom,email\nFDS,Faculté des Sciences,fds@example.ht\n"
            "FDS,Autre faculté,autre@example.ht\n",
            encoding="utf-8",
        )
        with self.assertRaises(CommandError):
            call_command("importer_entites", fichier=str(self.fichier), verbosity=0)
        self.assertFalse(Entite.objects.exists())


class ImportOptionsCsvTests(TestCase):
    def setUp(self):
        self.repertoire = TemporaryDirectory()
        self.addCleanup(self.repertoire.cleanup)
        self.fichier = Path(self.repertoire.name) / "options.csv"
        self.entite = Entite.objects.create(code="FDS", nom="Faculté des Sciences")

    def test_import_est_idempotent_et_preserve_les_options_existantes(self):
        from applications.entites.models import Option

        option_existante = Option.objects.create(
            entite=self.entite, nom="Physique", active=False
        )
        self.fichier.write_text(
            "code_entite,nom\nFDS,Physique\nFDS,Mathématiques\n",
            encoding="utf-8",
        )

        call_command("importer_options", fichier=str(self.fichier), verbosity=0)
        call_command("importer_options", fichier=str(self.fichier), verbosity=0)

        option_existante.refresh_from_db()
        self.assertFalse(option_existante.active)
        self.assertEqual(self.entite.options.count(), 2)
        self.assertTrue(self.entite.options.get(nom="Mathématiques").active)

    def test_code_entite_inconnu_ne_cree_aucune_option_partielle(self):
        from applications.entites.models import Option

        self.fichier.write_text(
            "code_entite,nom\nFDS,Physique\nINCONNUE,Option\n",
            encoding="utf-8",
        )

        with self.assertRaises(CommandError):
            call_command("importer_options", fichier=str(self.fichier), verbosity=0)

        self.assertFalse(Option.objects.exists())


class ConfigurerHorairesEntitesTests(TestCase):
    def test_active_am_et_pm_pour_toutes_les_entites_de_facon_idempotente(self):
        from applications.entites.models import HoraireEntite

        entite_a = Entite.objects.create(code="FDS", nom="Faculté des Sciences")
        entite_b = Entite.objects.create(code="FMP", nom="Médecine et Pharmacie")
        entite_b.inscription_ouverte = False
        entite_b.save(update_fields=["inscription_ouverte"])
        HoraireEntite.objects.create(
            entite=entite_a,
            code=HoraireEntite.Code.AM,
            actif=False,
        )

        call_command("configurer_horaires_entites", verbosity=0)
        call_command("configurer_horaires_entites", verbosity=0)

        for entite in (entite_a, entite_b):
            self.assertCountEqual(
                list(entite.horaires.filter(actif=True).values_list("code", flat=True)),
                [HoraireEntite.Code.AM, HoraireEntite.Code.PM],
            )
        entite_b.refresh_from_db()
        self.assertFalse(entite_b.inscription_ouverte)
        self.assertEqual(HoraireEntite.objects.count(), 4)
