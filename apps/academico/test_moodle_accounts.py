from io import BytesIO
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from apps.core.current_user import set_current_request
from apps.core.models import Partner, TipoIdentificacion
from .models import Curso, Materia, MateriaCurso, MoodleCuenta, MoodleCurso, MoodleMatricula
from .moodle import MoodleError
from .moodle_accounts import ensure_account, initial_password, username_base
from .moodle_exports import access_workbook


@override_settings(MOODLE_INITIAL_PASSWORD="Inicial-Test-123!", SECRET_KEY="test-key")
class MoodleAccountsTests(TestCase):
    def setUp(self):
        set_current_request(None)
        tipo = TipoIdentificacion.objects.create(nombre="Cédula", codigo="TEST")
        self.person = Partner.objects.create(nombre="Juan", apellido="Pérez", email="juan@example.org",
                                            identificacion="0000123", tipo_identificacion=tipo)
        self.client_api = MagicMock()
        self.client_api.base_url = "https://moodle.example"
        self.client_api.users_by_field.return_value = []
        self.client_api.create_users.side_effect = lambda users: [{"id": 42, "username": users[0]["username"]}]
        self.course = MateriaCurso.objects.create(materia=Materia.objects.create(nombre="Matemática"),
                                                 grupo=Curso.objects.create(nombre="Grupo A"))

    def test_username_suffix_and_forced_initial_password(self):
        self.assertEqual(username_base(self.person), "juan_perez")
        self.client_api.users_by_field.side_effect = [[], [{"id": 9, "username": "juan_perez"}], [], []]
        account = ensure_account(self.client_api, self.person)
        self.assertEqual(account.usuario, "juan_perez1")
        payload = self.client_api.create_users.call_args.args[0][0]
        self.assertEqual(payload["password"], "Inicial-Test-123!")
        self.assertIn({"type": "auth_forcepasswordchange", "value": "1"}, payload["preferences"])
        self.assertNotIn("Inicial-Test-123!", account.clave_inicial_cifrada)
        self.assertEqual(initial_password(account), "Inicial-Test-123!")

    def test_existing_account_is_linked_without_password_reset(self):
        self.client_api.users_by_field.return_value = [{"id": 21, "username": "usuario_previo"}]
        account = ensure_account(self.client_api, self.person)
        self.assertEqual(account.usuario, "usuario_previo")
        self.assertEqual(initial_password(account), "")
        ensure_account(self.client_api, self.person)
        self.client_api.create_users.assert_not_called()
        self.assertEqual(self.client_api.users_by_field.call_args.args, ("id", [21]))

    def test_timeout_preserves_reserved_username_and_initial_password(self):
        self.client_api.create_users.side_effect = MoodleError("Timeout")
        with self.assertRaises(MoodleError):
            ensure_account(self.client_api, self.person)
        account = MoodleCuenta.objects.get(persona=self.person)
        self.client_api.users_by_field.return_value = [{"id": 42, "username": account.usuario,
                                                        "idnumber": "instituto-" + str(account.clave)}]
        account = ensure_account(self.client_api, self.person)
        self.assertEqual(account.usuario_id, 42)
        self.assertEqual(self.client_api.create_users.call_count, 1)
        self.assertEqual(initial_password(account), "Inicial-Test-123!")

    def test_reserved_username_is_not_linked_to_another_remote_person(self):
        self.client_api.create_users.side_effect = MoodleError("Timeout")
        with self.assertRaises(MoodleError):
            ensure_account(self.client_api, self.person)
        self.client_api.users_by_field.return_value = [{"id": 99, "username": "juan_perez", "idnumber": "other"}]
        with self.assertRaises(MoodleError):
            ensure_account(self.client_api, self.person)
        self.assertIsNone(MoodleCuenta.objects.get(persona=self.person).usuario_id)

    def test_excel_contains_initial_access_as_text_and_requires_director_permission(self):
        account = ensure_account(self.client_api, self.person)
        link = MoodleCurso.objects.create(materia_curso=self.course, sitio=self.client_api.base_url, curso_id=7)
        MoodleMatricula.objects.create(curso=link, cuenta=account, rol="Alumno", confirmada=True)
        self.person.nombre = '=HYPERLINK("https://example.org")'
        self.person.save(update_fields=["nombre"])
        workbook = load_workbook(BytesIO(access_workbook(self.course)))
        sheet = workbook.active
        self.assertEqual(sheet["F2"].value, "juan_perez")
        self.assertEqual(sheet["G2"].value, "Inicial-Test-123!")
        self.assertEqual(sheet["C2"].data_type, "s")
        self.assertEqual(sheet["D2"].value, "0000123")
        user = get_user_model().objects.create_user(username="director_excel", password="Test-123!")
        url = reverse("academico:moodle_accesos_excel", args=[self.course.pk])
        self.client.force_login(user)
        self.assertEqual(self.client.get(url, HTTP_HOST="localhost").status_code, 403)
        user.groups.add(Group.objects.get(name="Director"))
        response = self.client.get(url, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertFalse(Group.objects.get(name="Coordinacion").permissions.filter(codename="exportar_moodlecuenta").exists())

    @override_settings(MOODLE_FALLBACK_EMAIL_DOMAIN="felixiot.site")
    def test_missing_email_uses_username_for_students_and_teachers(self):
        for email, role in [(None, "es_estudiante"), ("   ", "es_docente")]:
            with self.subTest(role=role):
                MoodleCuenta.objects.all().delete()
                self.person.email = email
                setattr(self.person, role, True)
                self.person.save()
                self.client_api.reset_mock()
                account = ensure_account(self.client_api, self.person)
                payload = self.client_api.create_users.call_args.args[0][0]
                self.assertEqual(payload["email"], "juan_perez@felixiot.site")
                self.assertEqual(account.usuario, "juan_perez")
                self.person.refresh_from_db()
                self.assertEqual(self.person.email, email)

    @override_settings(MOODLE_FALLBACK_EMAIL_DOMAIN="felixiot.site")
    def test_existing_provisional_email_gets_number_not_reused_account(self):
        self.person.email = ""
        self.client_api.users_by_field.side_effect = lambda field, values: (
            [{"id": 99, "username": "another_person"}]
            if field == "email" and values == ["juan_perez@felixiot.site"] else []
        )
        account = ensure_account(self.client_api, self.person)
        self.assertEqual(account.usuario, "juan_perez1")
        self.assertEqual(self.client_api.create_users.call_args.args[0][0]["email"], "juan_perez1@felixiot.site")

    def test_registered_email_is_preserved(self):
        ensure_account(self.client_api, self.person)
        self.assertEqual(self.client_api.create_users.call_args.args[0][0]["email"], "juan@example.org")

    def test_course_validation_allows_empty_email_but_rejects_invalid_email(self):
        from .models import ProfesorMateriaCurso
        from .moodle_courses import course_data
        self.person.email = None
        self.person.activo = True
        self.person.save()
        ProfesorMateriaCurso.objects.create(partner=self.person, materia_curso=self.course)
        self.assertFalse(any("correo" in error for error in course_data(self.course)["errors"]))
        self.person.email = "invalid-email"
        self.person.save()
        self.assertTrue(any("correo registrado no es válido" in error for error in course_data(self.course)["errors"]))

    def test_structure_creates_named_sections_and_subsections(self):
        from types import SimpleNamespace
        from .moodle_courses import sync_course_structure

        subtopics = MagicMock()
        subtopics.all.return_value = [
            SimpleNamespace(pk=2, orden=2, nombre="Enteros"),
            SimpleNamespace(pk=1, orden=1, nombre="Naturales"),
        ]
        topic = SimpleNamespace(nombre="Números", subtemas_planificacion=subtopics)
        api = MagicMock()
        api.course_state.side_effect = [
            {"section": [{"id": "1", "section": 0, "component": None, "cmlist": []}], "cm": []},
            {"section": [{"id": 1, "section": 0, "component": "", "cmlist": []},
                         {"id": 11, "section": 1, "component": "", "rawtitle": "", "cmlist": []}], "cm": []},
            {"section": [], "cm": []},
            {"section": [], "cm": [{"id": 31, "module": "subsection", "name": "Subtema 1.1: Naturales"},
                                     {"id": 32, "module": "subsection", "name": "Subtema 1.2: Enteros"}]},
        ]
        api.create_subsection.side_effect = [{"id": 31}, {"id": 32}]

        sync_course_structure(api, 7, [topic])

        api.add_section.assert_called_once_with(7)
        api.rename_section.assert_called_once_with(11, "Tema 1: Números")
        self.assertEqual(api.rename_activity.call_args_list[0].args, (31, "Subtema 1.1: Naturales"))
        self.assertEqual(api.rename_activity.call_args_list[1].args, (32, "Subtema 1.2: Enteros"))

    def test_math_syllabus_command_is_complete_and_idempotent(self):
        from .models import MateriaSubtema, MateriaTema, Subtema, Tema

        call_command("cargar_temario_matematicas", verbosity=0)
        call_command("cargar_temario_matematicas", verbosity=0)

        topics = MateriaTema.objects.filter(materia=self.course.materia)
        self.assertEqual(topics.count(), 10)
        self.assertEqual(MateriaSubtema.objects.filter(tema__in=topics).count(), 50)
        self.assertEqual(TopicNames := list(topics.order_by("orden").values_list("nombre", flat=True)), [
            "Tema 1: Conjuntos y lógica matemática",
            "Tema 2: Números reales y operaciones",
            "Tema 3: Razones, proporciones y porcentajes",
            "Tema 4: Expresiones algebraicas",
            "Tema 5: Ecuaciones e inecuaciones",
            "Tema 6: Funciones y gráficas",
            "Tema 7: Geometría plana y del espacio",
            "Tema 8: Trigonometría básica",
            "Tema 9: Estadística descriptiva",
            "Tema 10: Probabilidad y razonamiento matemático",
        ])
        self.assertEqual(len(TopicNames), Tema.objects.filter(planificacion__materia_curso=self.course).count())
        self.assertEqual(Subtema.objects.filter(tema__planificacion__materia_curso=self.course).count(), 50)
