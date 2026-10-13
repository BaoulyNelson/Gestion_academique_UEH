from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from applications.comptes.models import SiteConfiguration, Utilisateur


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ContactPageTests(TestCase):
    def setUp(self):
        self.configuration = SiteConfiguration.objects.create(
            nom_site="Institut Lumiere",
            slogan="Apprendre ensemble",
            email_contact="contact@institut.test",
        )

    def test_page_contact_publique_affiche_le_formulaire_et_le_logo(self):
        response = self.client.get(reverse("contact:contact"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contactez Institut Lumiere")
        self.assertContains(response, 'name="email"')
        self.assertContains(response, "public-footer-logo")
        self.assertContains(response, 'href="/admission/"')
        self.assertContains(response, 'class="public-header" id="accueil"')
        self.assertNotContains(response, 'class="barre-laterale"')

    def test_formulaire_valide_envoie_un_courriel_a_l_adresse_configuree(self):
        response = self.client.post(
            reverse("contact:contact"),
            {
                "nom": "Aline Jean",
                "email": "aline@example.test",
                "sujet": "Besoin d'aide",
                "message": "Je souhaite obtenir des renseignements.",
            },
        )

        self.assertRedirects(response, reverse("contact:contact"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["contact@institut.test"])
        self.assertEqual(mail.outbox[0].reply_to, ["aline@example.test"])
        self.assertIn("Je souhaite obtenir des renseignements.", mail.outbox[0].body)

    def test_formulaire_refuse_une_adresse_courriel_invalide(self):
        response = self.client.post(
            reverse("contact:contact"),
            {
                "nom": "Aline Jean",
                "email": "adresse-invalide",
                "sujet": "Question",
                "message": "Bonjour",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saisissez une adresse e-mail valide")
        self.assertEqual(mail.outbox, [])

    def test_page_contact_reste_publique_pour_un_utilisateur_connecte(self):
        utilisateur = Utilisateur.objects.create_user(
            username="contact-connecte",
            email="connecte@example.test",
            password="Mot-de-passe-123!",
        )
        self.client.force_login(utilisateur)

        response = self.client.get(reverse("contact:contact"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="barre-laterale"')
