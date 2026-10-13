from django.core.exceptions import ValidationError
from django.test import TestCase

from applications.candidats.models import Candidat
from applications.candidats.forms import NINUField, ProfilCandidatForm
from applications.candidats.etapes_forms import InformationsPersonnellesForm
from applications.comptes.models import Utilisateur
from applications.candidatures.models import Inscription
from applications.candidatures.forms import BrouillonInscriptionForm, InscriptionForm
from applications.entites.models import Entite, HoraireEntite, Option, Salle


class NINUFieldTests(TestCase):
    def test_ninu_est_numerique_et_limite_a_dix_chiffres_dans_les_formulaires(self):
        for formulaire in (ProfilCandidatForm, InformationsPersonnellesForm):
            champ = formulaire.base_fields["ninu"]
            with self.subTest(formulaire=formulaire.__name__):
                self.assertEqual(champ.widget.input_type, "text")
                self.assertEqual(champ.widget.attrs["maxlength"], "10")
                self.assertEqual(champ.widget.attrs["inputmode"], "numeric")
                self.assertEqual(champ.clean("0012345678"), "0012345678")
                for valeur in ("12345678901", "12A3", "-123", "12.3"):
                    with self.subTest(valeur=valeur):
                        with self.assertRaises(ValidationError):
                            champ.clean(valeur)


class NumerotationInscriptionTests(TestCase):
    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            "candidat@example.com", "MotDePasse-Securise-2026"
        )
        self.candidat = Candidat.objects.create(utilisateur=self.utilisateur)
        self.entite = Entite.objects.create(code="FDS", nom="Faculté des Sciences")

    def creer_inscription(self, entite=None):
        return Inscription.objects.create(
            candidat=self.candidat,
            entite=entite or self.entite,
            annee_academique="2026-2027",
        )

    def test_numero_et_rangs_des_trois_inscriptions(self):
        entites = [
            self.entite,
            Entite.objects.create(code="FASCH", nom="Sciences humaines"),
            Entite.objects.create(code="FMP", nom="Médecine et pharmacie"),
        ]
        inscriptions = [self.creer_inscription(entite) for entite in entites]
        self.assertEqual([i.rang for i in inscriptions], [0, 1, 2])
        self.assertEqual(
            [i.numero_dossier for i in inscriptions],
            [self.candidat.pk * 100 + n for n in range(3)],
        )

    def test_numeros_de_candidats_differents_ne_se_chevauchent_pas(self):
        autre_utilisateur = Utilisateur.objects.create_user(
            "autre-candidat@example.com", "MotDePasse-Securise-2026"
        )
        autre_candidat = Candidat.objects.create(utilisateur=autre_utilisateur)
        inscription_a = self.creer_inscription()
        inscription_b = Inscription.objects.create(
            candidat=autre_candidat,
            entite=self.entite,
            annee_academique="2026-2027",
        )
        self.assertNotEqual(inscription_a.numero_dossier, inscription_b.numero_dossier)

    def test_quatrieme_inscription_refusee(self):
        for numero, (code, nom) in enumerate(
            [
                ("FDS", "Faculté des Sciences"),
                ("FASCH", "Sciences humaines"),
                ("FMP", "Médecine et pharmacie"),
            ]
        ):
            entite = (
                self.entite
                if numero == 0
                else Entite.objects.create(code=code, nom=nom)
            )
            self.creer_inscription(entite)
        with self.assertRaises(
            ValidationError, msg="La limite doit être expliquée en français."
        ):
            entite = Entite.objects.create(code="FSEA", nom="Sciences de l'éducation")
            self.creer_inscription(entite)

    def test_rang_libere_reutilise(self):
        entites = [
            self.entite,
            Entite.objects.create(code="FASCH", nom="Sciences humaines"),
            Entite.objects.create(code="FMP", nom="Médecine et pharmacie"),
        ]
        inscriptions = [self.creer_inscription(entite) for entite in entites]
        numero = inscriptions[1].numero_dossier
        inscriptions[1].delete()
        nouvelle_entite = Entite.objects.create(
            code="FSEA", nom="Sciences de l'éducation"
        )
        nouvelle = self.creer_inscription(nouvelle_entite)
        self.assertEqual(nouvelle.rang, 1)
        self.assertEqual(nouvelle.numero_dossier, numero)

    def test_meme_entite_ne_peut_etre_inscrite_quune_fois(self):
        self.creer_inscription()
        with self.assertRaises(ValidationError):
            self.creer_inscription()


class ContraintesEntiteTests(TestCase):
    def setUp(self):
        utilisateur = Utilisateur.objects.create_user(
            "profil@example.com", "MotDePasse-Securise-2026"
        )
        self.candidat = Candidat.objects.create(utilisateur=utilisateur)
        self.entite_a = Entite.objects.create(code="FDS", nom="Faculté des Sciences")
        self.entite_b = Entite.objects.create(code="FASCH", nom="Sciences humaines")

    def test_references_seq_et_till_sont_numeriques(self):
        for formulaire in (InscriptionForm(), BrouillonInscriptionForm()):
            for nom in ("seq", "till"):
                champ = formulaire.fields[nom]
                self.assertEqual(champ.widget.input_type, "number")
                with self.assertRaises(ValidationError):
                    champ.clean("12A")

    def test_horaire_doit_etre_propose_par_l_entite(self):
        HoraireEntite.objects.create(entite=self.entite_a, code=HoraireEntite.Code.AM)
        inscription = Inscription.objects.create(
            candidat=self.candidat,
            entite=self.entite_a,
            annee_academique="2026-2027",
            horaire=Inscription.Horaire.AM,
        )
        self.assertEqual(inscription.horaire, Inscription.Horaire.AM)
        with self.assertRaises(ValidationError):
            Inscription.objects.create(
                candidat=self.candidat,
                entite=self.entite_a,
                annee_academique="2026-2027",
                horaire=Inscription.Horaire.PM,
            )

    def test_option_et_salle_d_une_autre_entite_sont_refusees(self):
        option = Option.objects.create(entite=self.entite_b, nom="Mathématiques")
        salle = Salle.objects.create(entite=self.entite_b, nom="Salle B")
        with self.assertRaises(ValidationError):
            Inscription.objects.create(
                candidat=self.candidat,
                entite=self.entite_a,
                option=option,
                annee_academique="2026-2027",
            )
        with self.assertRaises(ValidationError):
            Inscription.objects.create(
                candidat=self.candidat,
                entite=self.entite_a,
                salle=salle,
                annee_academique="2026-2027",
            )

    def test_numero_et_rang_sont_immuables_apres_creation(self):
        inscription = Inscription.objects.create(
            candidat=self.candidat,
            entite=self.entite_a,
            annee_academique="2026-2027",
        )
        inscription.numero_dossier += 1
        with self.assertRaises(ValidationError):
            inscription.save()
        with self.assertRaises(ValidationError):
            Inscription.objects.filter(pk=inscription.pk).update(numero_dossier=123)
        with self.assertRaises(ValidationError):
            Inscription.objects.bulk_update([inscription], ["numero_dossier"])
        with self.assertRaises(ValidationError):
            Inscription.objects.bulk_create([inscription])
