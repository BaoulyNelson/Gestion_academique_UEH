from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings


class AdmissionProxyTests(SimpleTestCase):
    @override_settings(DEBUG=True)
    @patch("config.admission_proxy.HTTPConnection")
    def test_relaie_la_requete_et_les_cookies_vers_admission(self, connection_class):
        upstream_response = Mock(
            status=200,
            reason="OK",
            read=Mock(return_value=b"Admission"),
            getheaders=Mock(
                return_value=[
                    ("Content-Type", "text/html"),
                    ("Set-Cookie", "admission_sessionid=abc; Path=/admission/; HttpOnly"),
                ]
            ),
        )
        connection = connection_class.return_value
        connection.getresponse.return_value = upstream_response

        response = self.client.get(
            "/admission/candidatures/",
            {"page": "2"},
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Admission")
        self.assertEqual(
            response.cookies["admission_sessionid"]["path"],
            "/admission/",
        )
        connection.request.assert_called_once()
        self.assertEqual(
            connection.request.call_args.args[:2],
            ("GET", "/candidatures/?page=2"),
        )
        self.assertEqual(
            connection.request.call_args.kwargs["headers"]["X-Forwarded-Prefix"],
            "/admission",
        )

    @override_settings(DEBUG=True)
    @patch("config.admission_proxy.HTTPConnection")
    def test_retourne_une_erreur_502_si_admission_n_est_pas_lance(self, connection_class):
        connection_class.side_effect = OSError("Connexion refusee")

        response = self.client.get("/admission/")

        self.assertEqual(response.status_code, 502)
        self.assertContains(response, "Lancez-le sur le port 8001.", status_code=502)

    @override_settings(DEBUG=False)
    @patch("config.admission_proxy.HTTPConnection")
    def test_proxy_de_developpement_est_inactif_hors_debug(self, connection_class):
        response = self.client.get("/admission/")

        self.assertEqual(response.status_code, 404)
        connection_class.assert_not_called()
