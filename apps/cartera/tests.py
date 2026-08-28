from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.current_user import set_current_request
from apps.core.models import Empresa

from .forms import FormaPagoForm
from .models import FormaPago


class FormaPagoFormTests(TestCase):
    def setUp(self):
        set_current_request(None)
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="ClaveActual987!",
        )
        self.empresa = Empresa.objects.create(
            ruc="1790000000001",
            razon_social="Instituto Prueba",
            nombre_comercial="Instituto Prueba",
            activa=True,
        )

    def tearDown(self):
        set_current_request(None)

    def test_form_only_exposes_business_fields_and_saves_internal_defaults(self):
        form = FormaPagoForm(
            data={
                "empresa": self.empresa.pk,
                "nombre": "Transferencia",
                "activo": "on",
            }
        )

        self.assertEqual(list(form.fields), ["empresa", "nombre", "activo"])
        self.assertTrue(form.is_valid(), form.errors)
        forma_pago = form.save()
        self.assertEqual(forma_pago.tipo, "transferencia")
        self.assertEqual(forma_pago.orden, 1)
        self.assertTrue(forma_pago.es_venta)
        self.assertTrue(forma_pago.es_pago)
        self.assertTrue(forma_pago.activo)

    def test_payment_method_page_hides_internal_fields(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("cartera:forma_pago_nueva"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Efectivo")
        self.assertContains(response, "Tarjeta")
        self.assertNotContains(response, "Es venta")
        self.assertNotContains(response, "Es pago")
        self.assertNotContains(response, "Orden")
        self.assertNotContains(response, 'name="tipo"')

    def test_generic_active_fields_render_switch_style(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("matricula:periodo_nuevo"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "switchery.min.css")
        self.assertContains(response, "switch-field")
        self.assertContains(response, "js-switch")

    def test_duplicate_name_is_rejected_per_company(self):
        FormaPago.objects.create(
            empresa=self.empresa,
            nombre="Efectivo",
            tipo="efectivo",
            es_venta=True,
            es_pago=True,
            activo=True,
        )

        form = FormaPagoForm(
            data={
                "empresa": self.empresa.pk,
                "nombre": "Efectivo",
                "activo": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("nombre", form.errors)
