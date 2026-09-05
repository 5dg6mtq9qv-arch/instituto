import io
import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from apps.academico.moodle import MoodleClient, MoodleError, NoRedirects, REQUIRED_FUNCTIONS


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
