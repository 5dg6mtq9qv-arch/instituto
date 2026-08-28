from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from apps.core.forms import SystemUserForm
from apps.core.current_user import set_current_request
from apps.core.models import Empresa, Partner, TipoIdentificacion


class SystemUserFormPasswordTests(TestCase):
    def setUp(self):
        set_current_request(None)

    def tearDown(self):
        set_current_request(None)

    def form_data(self, user, password=""):
        return {
            "username": user.username,
            "first_name": "Usuario",
            "last_name": "Prueba",
            "email": "usuario@example.com",
            "is_active": "on",
            "password": password,
            "groups": [],
        }

    def test_blank_password_keeps_existing_hash_on_edit(self):
        user = get_user_model().objects.create_user(username="usuario", password="ClaveActual987!")
        original_hash = user.password

        form = SystemUserForm(data=self.form_data(user), instance=user)

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        user.refresh_from_db()
        self.assertEqual(user.password, original_hash)
        self.assertTrue(user.check_password("ClaveActual987!"))

    def test_password_value_updates_hash_on_edit(self):
        user = get_user_model().objects.create_user(username="usuario", password="ClaveActual987!")
        original_hash = user.password

        form = SystemUserForm(data=self.form_data(user, password="NuevaClave987!"), instance=user)

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        user.refresh_from_db()
        self.assertNotEqual(user.password, original_hash)
        self.assertTrue(user.check_password("NuevaClave987!"))


class MiPerfilPasswordTests(TestCase):
    def setUp(self):
        set_current_request(None)

    def tearDown(self):
        set_current_request(None)

    def test_user_without_partner_can_change_own_password(self):
        user = get_user_model().objects.create_user(username="sinperfil", password="ClaveActual987!")
        self.client.force_login(user)

        response = self.client.get(reverse("core:mi_perfil"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cambiar contraseña")

        response = self.client.post(
            reverse("core:mi_perfil"),
            {
                "form_type": "password",
                "old_password": "ClaveActual987!",
                "new_password1": "NuevaClave987!",
                "new_password2": "NuevaClave987!",
            },
            HTTP_HOST="localhost",
        )

        self.assertRedirects(response, reverse("core:mi_perfil"), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NuevaClave987!"))


class DashboardPersonalizationTests(TestCase):
    def setUp(self):
        set_current_request(None)
        self.tipo_identificacion = TipoIdentificacion.objects.create(nombre="Cedula", codigo="CED")

    def tearDown(self):
        set_current_request(None)

    def test_docente_dashboard_uses_teacher_profile(self):
        user = get_user_model().objects.create_user(username="docente", password="ClaveActual987!")
        Partner.objects.create(
            tipo_identificacion=self.tipo_identificacion,
            identificacion="DOC-100",
            nombre="Docente Dashboard",
            usuario=user,
            es_docente=True,
            activo=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_profile"]["role"], "docente")
        self.assertContains(response, "Panel docente")
        self.assertContains(response, "Mis clases")
        self.assertContains(response, "Calendario")

    def test_coordinacion_dashboard_uses_review_profile(self):
        user = get_user_model().objects.create_user(username="coordinador", password="ClaveActual987!")
        user.groups.add(Group.objects.get_or_create(name="Coordinacion")[0])
        self.client.force_login(user)

        response = self.client.get(reverse("home"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_profile"]["role"], "coordinacion")
        self.assertContains(response, "Panel de coordinacion")
        self.assertContains(response, "Por revisar")
        self.assertContains(response, "Revision docente")

    def test_director_dashboard_uses_institutional_pending_profile(self):
        user = get_user_model().objects.create_user(username="director", password="ClaveActual987!")
        user.groups.add(Group.objects.get_or_create(name="Director")[0])
        self.client.force_login(user)

        response = self.client.get(reverse("home"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_profile"]["role"], "direccion")
        self.assertContains(response, "Panel directivo")
        self.assertContains(response, "Clases sin docente")
        self.assertContains(response, "Cartera")


class PartnerRoleViewTests(TestCase):
    def setUp(self):
        set_current_request(None)
        self.empresa = Empresa.objects.create(
            ruc="1790000000001",
            razon_social="Instituto Prueba",
            nombre_comercial="Instituto Prueba",
            activa=True,
        )
        self.tipo_identificacion = TipoIdentificacion.objects.create(nombre="Cedula", codigo="CED", activo=True)
        self.user = get_user_model().objects.create_user(username="operador", password="ClaveActual987!")
        self.user.user_permissions.add(
            Permission.objects.get(codename="view_partner"),
            Permission.objects.get(codename="add_partner"),
            Permission.objects.get(codename="change_partner"),
        )
        self.estudiante = Partner.objects.create(
            empresa=self.empresa,
            tipo_identificacion=self.tipo_identificacion,
            identificacion="1002003001",
            nombre="Alumno Uno",
            telefono_celular="0991112222",
            email="alumno@example.com",
            es_estudiante=True,
            activo=True,
        )
        self.representante = Partner.objects.create(
            empresa=self.empresa,
            tipo_identificacion=self.tipo_identificacion,
            identificacion="1002003002",
            nombre="Representante Uno",
            telefono_celular="0993334444",
            email="representante@example.com",
            es_cliente=True,
            es_representante=True,
            activo=True,
        )
        self.docente = Partner.objects.create(
            empresa=self.empresa,
            tipo_identificacion=self.tipo_identificacion,
            identificacion="1002003003",
            nombre="Docente Uno",
            es_docente=True,
            activo=True,
        )

    def tearDown(self):
        set_current_request(None)

    def test_students_and_representatives_have_separate_readable_lists_without_create_button(self):
        self.client.force_login(self.user)

        students_response = self.client.get(reverse("core:estudiante_list"), HTTP_HOST="localhost")
        representatives_response = self.client.get(reverse("core:representante_list"), HTTP_HOST="localhost")

        self.assertEqual(students_response.status_code, 200)
        self.assertContains(students_response, "Estudiantes")
        self.assertContains(students_response, "Alumno Uno")
        self.assertNotContains(students_response, "Representante Uno")
        self.assertNotContains(students_response, "list-create-btn")
        self.assertNotContains(students_response, "True")

        self.assertEqual(representatives_response.status_code, 200)
        self.assertContains(representatives_response, "Representantes")
        self.assertContains(representatives_response, "Representante Uno")
        self.assertNotContains(representatives_response, "Alumno Uno")
        self.assertNotContains(representatives_response, "list-create-btn")

    def test_student_and_representative_edit_forms_do_not_expose_role_flags(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("core:estudiante_editar", kwargs={"pk": self.estudiante.pk}),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="es_estudiante"')
        self.assertNotContains(response, 'name="es_representante"')
        self.assertNotContains(response, 'name="es_docente"')

    def test_generic_partner_create_is_blocked_even_with_add_permission(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("core:partner_nuevo"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 403)

    def test_legacy_partner_list_redirects_to_students(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("core:partner_list"), HTTP_HOST="localhost")

        self.assertRedirects(response, reverse("core:estudiante_list"), fetch_redirect_response=False)

    def test_director_can_create_docente_but_not_system_user(self):
        director = get_user_model().objects.create_user(username="director", password="ClaveActual987!")
        director.groups.add(Group.objects.get_or_create(name="Director")[0])
        self.client.force_login(director)

        user_response = self.client.get(reverse("core:usuario_nuevo"), HTTP_HOST="localhost")
        self.assertEqual(user_response.status_code, 403)

        form_response = self.client.get(reverse("core:docente_nuevo"), HTTP_HOST="localhost")
        self.assertEqual(form_response.status_code, 200)
        self.assertContains(form_response, "Acceso docente")
        self.assertContains(form_response, 'name="username"')
        self.assertContains(form_response, 'name="password"')
        self.assertNotContains(form_response, 'name="es_docente"')
        self.assertNotContains(form_response, 'name="es_estudiante"')
        self.assertNotContains(form_response, 'name="es_representante"')

        response = self.client.post(
            reverse("core:docente_nuevo"),
            {
                "empresa": self.empresa.pk,
                "tipo_identificacion": self.tipo_identificacion.pk,
                "identificacion": "1002003004",
                "nombre": "Docente Nuevo",
                "username": "docente_nuevo",
                "password": "ClaveDocente987!",
                "password_confirm": "ClaveDocente987!",
                "telefono": "",
                "telefono_celular": "0994445555",
                "email": "docente@example.com",
                "fecha_nacimiento": "",
                "genero": "",
                "ocupacion": "Docente",
                "direccion": "",
                "activo": "on",
            },
            HTTP_HOST="localhost",
        )

        self.assertRedirects(response, reverse("core:docente_list"), fetch_redirect_response=False)
        docente = Partner.objects.get(identificacion="1002003004")
        self.assertTrue(docente.es_docente)
        self.assertFalse(docente.es_estudiante)
        self.assertFalse(docente.es_representante)
        self.assertFalse(docente.es_cliente)
        self.assertIsNotNone(docente.usuario)
        self.assertEqual(docente.usuario.username, "docente_nuevo")
        self.assertTrue(docente.usuario.check_password("ClaveDocente987!"))
        self.assertTrue(docente.usuario.groups.filter(name="Docente").exists())
