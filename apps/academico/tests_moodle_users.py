from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.academico.models import MoodleCuenta
from apps.academico.moodle_users import (
    suspend_inactive_student,
    suspend_inactive_students,
)
from apps.core.models import Partner, TipoIdentificacion


class MoodleInactiveStudentsTests(TestCase):
    def setUp(self):
        identification_type = TipoIdentificacion.objects.create(nombre="Cedula")
        self.inactive_student = Partner.objects.create(
            nombre="Alumno Inactivo",
            identificacion="MOODLE-INACTIVO-1",
            tipo_identificacion=identification_type,
            es_estudiante=True,
            activo=False,
        )
        self.active_student = Partner.objects.create(
            nombre="Alumno Activo",
            identificacion="MOODLE-ACTIVO-1",
            tipo_identificacion=identification_type,
            es_estudiante=True,
            activo=True,
        )
        MoodleCuenta.objects.create(
            persona=self.inactive_student,
            sitio="https://moodle.example",
            usuario="alumno_inactivo",
            usuario_id=101,
        )
        MoodleCuenta.objects.create(
            persona=self.active_student,
            sitio="https://moodle.example",
            usuario="alumno_activo",
            usuario_id=102,
        )

    def test_simulation_does_not_modify_moodle(self):
        client = MagicMock(base_url="https://moodle.example")

        accounts = suspend_inactive_students(client=client)

        self.assertEqual([account.usuario_id for account in accounts], [101])
        client.update_users.assert_not_called()

    def test_apply_suspends_only_inactive_students(self):
        client = MagicMock(base_url="https://moodle.example")

        accounts = suspend_inactive_students(client=client, apply=True)

        self.assertEqual([account.usuario_id for account in accounts], [101])
        client.update_users.assert_called_once_with([{"id": 101, "suspended": 1}])

    def test_single_account_is_revalidated_before_suspension(self):
        client = MagicMock(base_url="https://moodle.example")
        client.users_by_field.return_value = [{"id": 101, "suspended": 1}]
        account = MoodleCuenta.objects.get(persona=self.inactive_student)

        result = suspend_inactive_student(account.pk, client=client)

        self.assertEqual(result, account)
        client.update_users.assert_called_once_with([{"id": 101, "suspended": 1}])
        client.users_by_field.assert_called_once_with("id", [101])

    @patch("apps.academico.management.commands.sincronizar_estudiantes_inactivos_moodle.MoodleClient")
    def test_command_is_a_simulation_by_default(self, client_factory):
        client_factory.return_value.base_url = "https://moodle.example"
        output = StringIO()

        call_command("sincronizar_estudiantes_inactivos_moodle", stdout=output)

        client_factory.return_value.update_users.assert_not_called()
        self.assertIn("Simulacion: 1 cuenta(s)", output.getvalue())


class MoodleInactiveStudentsButtonTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="moodle_sync_user",
            password="test-password",
        )
        self.list_url = reverse("core:estudiante_list")
        self.sync_url = reverse("core:sincronizar_estudiantes_inactivos_moodle")

    def test_button_requires_moodle_suspension_permission(self):
        self.client.force_login(self.user)

        response = self.client.get(self.list_url, HTTP_HOST="localhost")

        self.assertNotContains(response, "Desactivar inactivos en Moodle")
        self.assertEqual(
            self.client.post(self.sync_url, HTTP_HOST="localhost").status_code,
            403,
        )

    @patch("apps.academico.moodle_users.suspend_inactive_students")
    def test_button_suspends_students_and_returns_to_list(self, suspend_students):
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="academico",
                codename="suspender_inactivos_moodlecuenta",
            )
        )
        self.client.force_login(self.user)
        suspend_students.return_value = [MagicMock(), MagicMock()]

        page = self.client.get(self.list_url, HTTP_HOST="localhost")
        response = self.client.post(self.sync_url, HTTP_HOST="localhost")

        self.assertContains(page, "Desactivar inactivos en Moodle")
        self.assertContains(page, "sweetalert2@11")
        self.assertNotContains(page, "return confirm(")
        self.assertRedirects(response, self.list_url, fetch_redirect_response=False)
        suspend_students.assert_called_once_with(apply=True)
