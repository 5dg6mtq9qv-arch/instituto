from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.forms import SystemUserForm
from apps.core.current_user import set_current_request


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
