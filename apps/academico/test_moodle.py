import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.academico.models import MoodleConfiguracion
from apps.academico.moodle import (
    MoodleClient,
    MoodleError,
    NoRedirects,
    REQUIRED_FUNCTIONS,
    decrypt_moodle_token,
    encrypt_moodle_token,
    normalize_moodle_url,
)
from apps.core.menu import permitted_menu_groups


@override_settings(MOODLE_BASE_URL="https://moodle.example", MOODLE_TOKEN="private-test-token", MOODLE_TIMEOUT=7)
class MoodleClientTests(SimpleTestCase):
    def client_with_response(self, body):
        client = MoodleClient()
        client.opener = MagicMock()
        client.opener.open.return_value.__enter__.return_value = io.BytesIO(body)
        return client

    def test_credentials_are_in_post_body_only(self):
        client = self.client_with_response(b'{"functions": []}')
        client.site_info()
        args, kwargs = client.opener.open.call_args
        self.assertNotIn("private-test-token", args[0])
        self.assertIn(b"wstoken=private-test-token", kwargs["data"])
        self.assertEqual(kwargs["timeout"], 7)

    def test_local_moodle_urls_allow_http(self):
        self.assertEqual(normalize_moodle_url("127.0.0.1/moodle"), "http://127.0.0.1/moodle")
        self.assertEqual(
            normalize_moodle_url("http://192.168.10.25/moodle/"),
            "http://192.168.10.25/moodle",
        )
        self.assertEqual(
            normalize_moodle_url("https://aula.solucionesintegrales.xyz/"),
            "https://aula.solucionesintegrales.xyz",
        )

    def test_public_http_and_credentials_in_url_are_rejected(self):
        with self.assertRaises(MoodleError):
            normalize_moodle_url("http://moodle.example.com")
        with self.assertRaises(MoodleError):
            normalize_moodle_url("https://user:secret@moodle.example.com")

    @override_settings(SECRET_KEY="test-secret", SECRET_KEY_FALLBACKS=[])
    def test_saved_token_is_encrypted_and_can_configure_client(self):
        encrypted = encrypt_moodle_token("private-test-token")
        self.assertNotIn("private-test-token", encrypted)
        self.assertEqual(decrypt_moodle_token(encrypted), "private-test-token")
        client = MoodleClient(configuration=SimpleNamespace(
            base_url="http://127.0.0.1/moodle",
            token_cifrado=encrypted,
        ))
        self.assertEqual(client.base_url, "http://127.0.0.1/moodle")
        self.assertEqual(client.token, "private-test-token")

    def test_remote_errors_do_not_disclose_response_or_token(self):
        client = self.client_with_response(b'{"exception":"error", "errorcode":"invalidtoken", "message":"private-test-token"}')
        with self.assertRaises(MoodleError) as caught:
            client.site_info()
        self.assertNotIn("private-test-token", str(caught.exception))

    def test_invalid_json_and_network_errors_are_safe(self):
        client = self.client_with_response(b'<html>private-test-token</html>')
        with self.assertRaises(MoodleError):
            client.site_info()
        for error in [URLError("private-test-token"), TimeoutError(), HTTPError("https://moodle.example", 403, "private-test-token", {}, None)]:
            client.opener.open.side_effect = error
            with self.assertRaises(MoodleError) as caught:
                client.site_info()
            self.assertNotIn("private-test-token", str(caught.exception))

    def test_http_errors_are_explained_without_technical_codes(self):
        client = self.client_with_response(b"{}")
        client.opener.open.side_effect = HTTPError("https://moodle.example", 403, "Forbidden", {}, None)

        with self.assertRaises(MoodleError) as caught:
            client.site_info()

        message = str(caught.exception)
        self.assertIn("no permitió la conexión", message)
        self.assertIn("token", message)
        self.assertNotIn("HTTP 403", message)

    def test_redirects_are_not_followed(self):
        self.assertIsNone(NoRedirects().redirect_request(None, None, 302, "", {}, "https://other.example"))

    @override_settings(MOODLE_TOKEN="")
    def test_missing_credentials_do_not_send_request(self):
        client = self.client_with_response(b'{}')
        with self.assertRaises(MoodleError):
            client.site_info()
        client.opener.open.assert_not_called()

    @patch("apps.academico.management.commands.comprobar_moodle.MoodleClient")
    def test_check_command_only_reads_site_and_categories(self, client_class):
        client = client_class.return_value
        client.site_info.return_value = {"release": "5.1.5+", "functions": [
            {"name": name} for name in ["core_webservice_get_site_info", "core_course_get_categories",
                                       "core_course_get_courses_by_field", "core_course_create_courses", "core_course_get_contents"]
        ]}
        client.missing_functions.return_value = []
        client.categories.return_value = [{"id": 1, "name": "Pruebas"}]
        output = io.StringIO()
        call_command("comprobar_moodle", stdout=output)
        self.assertIn("1: Pruebas", output.getvalue())
        self.assertEqual([call[0] for call in client.method_calls], ["site_info", "missing_functions", "categories"])

    def test_expanded_service_detects_missing_enrolment_function(self):
        client = MoodleClient()
        info = {"functions": [{"name": name} for name in REQUIRED_FUNCTIONS if name != "enrol_manual_enrol_users"]}
        self.assertEqual(client.missing_functions(info), ["enrol_manual_enrol_users"])

    def test_user_creation_encodes_nested_fields(self):
        client = self.client_with_response(b'[{"id": 15}]')
        self.assertEqual(client.create_users([{"username": "student", "firstname": "Ana", "lastname": "Perez"}]), [{"id": 15}])
        from urllib.parse import parse_qs
        payload = parse_qs(client.opener.open.call_args.kwargs["data"].decode())
        self.assertEqual(payload["users[0][username]"], ["student"])
        self.assertEqual(payload["wsfunction"], ["core_user_create_users"])

    def test_enrolment_encodes_role_and_course(self):
        client = self.client_with_response(b'null')
        client.enrol_users([{"roleid": 5, "userid": 15, "courseid": 8}])
        from urllib.parse import parse_qs
        payload = parse_qs(client.opener.open.call_args.kwargs["data"].decode())
        self.assertEqual(payload["enrolments[0][roleid]"], ["5"])
        self.assertEqual(payload["enrolments[0][courseid]"], ["8"])

    def test_user_lookup_rejects_unexpected_results(self):
        client = self.client_with_response(b'{"users": []}')
        with self.assertRaises(MoodleError):
            client.users_by_field("email", ["student@example.org"])

    def test_course_state_requires_valid_json_structure(self):
        client = self.client_with_response(b'"not-an-object"')
        with self.assertRaises(MoodleError):
            client.course_state(7)

    def test_add_section_uses_course_format_action(self):
        client = self.client_with_response(b'"{\\"section\\":[]}"')
        client.add_section(7)
        from urllib.parse import parse_qs
        payload = parse_qs(client.opener.open.call_args.kwargs["data"].decode())
        self.assertEqual(payload["action"], ["section_add"])
        self.assertEqual(payload["courseid"], ["7"])

    def test_section_and_activity_renames_use_inplace_api(self):
        client = self.client_with_response(b'{"displayvalue":"Tema"}')
        client.opener.open.return_value.__enter__.side_effect = [
            io.BytesIO(b'{"displayvalue":"Tema"}'),
            io.BytesIO(b'{"displayvalue":"Subtema"}'),
        ]
        client.rename_section(12, "Tema 1: Números")
        from urllib.parse import parse_qs
        payload = parse_qs(client.opener.open.call_args.kwargs["data"].decode())
        self.assertEqual(payload["component"], ["format_topics"])
        self.assertEqual(payload["itemtype"], ["sectionname"])
        client.rename_activity(18, "Subtema 1.1: Naturales")
        payload = parse_qs(client.opener.open.call_args.kwargs["data"].decode())
        self.assertEqual(payload["component"], ["core_course"])
        self.assertEqual(payload["itemtype"], ["activityname"])

    def test_subsection_id_is_read_from_course_update(self):
        body = json.dumps(json.dumps([
            {"name": "cm", "action": "put", "fields": {"id": "31", "module": "subsection", "sectionid": "11"}},
            {"name": "cm", "action": "put", "fields": {"id": "32", "module": "subsection", "sectionid": "11"}},
        ])).encode()
        client = self.client_with_response(body)
        self.assertEqual(client.create_subsection(7, 11)["id"], "32")

    def test_temario_summary_escapes_content_and_keeps_order(self):
        from types import SimpleNamespace
        from apps.academico.moodle_courses import temario_summary
        subtemas = MagicMock()
        subtemas.all.return_value = [SimpleNamespace(pk=1, orden=2, nombre="B"), SimpleNamespace(pk=2, orden=1, nombre="A")]
        tema = SimpleNamespace(nombre="<script>bad</script>", detalle="<img>", subtemas_planificacion=subtemas)
        summary = temario_summary([tema])
        self.assertNotIn("<script>", summary)
        self.assertIn("&lt;img&gt;", summary)
        self.assertLess(summary.index("<li>A</li>"), summary.index("<li>B</li>"))


@override_settings(SECRET_KEY="test-secret", SECRET_KEY_FALLBACKS=[])
class MoodleConfiguracionViewTests(TestCase):
    def setUp(self):
        self.admin_group = Group.objects.get_or_create(name="Administrador")[0]
        self.admin = get_user_model().objects.create_user(username="moodle_admin", password="Clave987!")
        self.admin.groups.add(self.admin_group)
        self.other_user = get_user_model().objects.create_user(username="moodle_other", password="Clave987!")
        self.url = reverse("academico:moodle_configuracion")

    def test_only_administrator_can_open_configuration_and_see_menu_link(self):
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(self.url, HTTP_HOST="localhost").status_code, 403)

        self.client.force_login(self.admin)
        response = self.client.get(self.url, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Guardar configuración")
        self.assertContains(response, "Probar conexión guardada")
        administrativo = next(
            group for group in permitted_menu_groups(self.admin) if group["label"] == "Administrativo"
        )
        self.assertIn("Configuración Moodle", [item["label"] for item in administrativo["items"]])

    def test_saves_encrypted_token_and_blank_token_keeps_it(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url,
            {"base_url": "https://aula.solucionesintegrales.xyz/", "token": "token-super-secreto", "action": "save"},
            HTTP_HOST="localhost",
        )
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        configuration = MoodleConfiguracion.objects.get()
        original = configuration.token_cifrado
        self.assertNotIn("token-super-secreto", original)
        self.assertEqual(decrypt_moodle_token(original), "token-super-secreto")

        self.client.post(
            self.url,
            {"base_url": "http://127.0.0.1/moodle", "token": "", "action": "save"},
            HTTP_HOST="localhost",
        )
        configuration.refresh_from_db()
        self.assertEqual(configuration.token_cifrado, original)
        self.assertEqual(configuration.base_url, "http://127.0.0.1/moodle")

    @patch("apps.academico.moodle.MoodleClient")
    def test_connection_button_records_result(self, client_class):
        client = client_class.return_value
        client.site_info.return_value = {
            "sitename": "Aula Instituto",
            "release": "5.1.5+",
            "functions": [{"name": name} for name in REQUIRED_FUNCTIONS],
        }
        client.missing_functions.return_value = []
        self.client.force_login(self.admin)
        self.client.post(
            self.url,
            {"base_url": "https://aula.solucionesintegrales.xyz", "token": "valid-token", "action": "save"},
            HTTP_HOST="localhost",
        )
        saved_token = MoodleConfiguracion.objects.get().token_cifrado
        response = self.client.post(
            self.url,
            {"action": "test", "base_url": "http://127.0.0.1/ignored", "token": "ignored-token"},
            HTTP_HOST="localhost",
        )

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        configuration = MoodleConfiguracion.objects.get()
        self.assertTrue(configuration.ultima_prueba_exitosa)
        self.assertIn("Aula Instituto", configuration.ultimo_resultado)
        self.assertEqual(configuration.base_url, "https://aula.solucionesintegrales.xyz")
        self.assertEqual(configuration.token_cifrado, saved_token)
        client_class.assert_called_once_with(configuration=configuration)
