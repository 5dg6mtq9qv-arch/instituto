from datetime import date, datetime
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.current_user import set_current_request
from apps.core.models import Empresa, Partner, TipoIdentificacion
from apps.matricula.models import FichaInscripcion

from .forms import FormaPagoForm
from .forms import PagoForm
from .models import Cuota, FormaPago, Pago, PlanPago


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

    def create_payment_flow_data(self):
        tipo_identificacion = TipoIdentificacion.objects.create(nombre="Cedula", codigo="CED")
        cliente = Partner.objects.create(
            nombre="Maria Representante",
            tipo_identificacion=tipo_identificacion,
            identificacion="0990000001",
            empresa=self.empresa,
            es_cliente=True,
        )
        estudiante = Partner.objects.create(
            nombre="Juan Estudiante",
            tipo_identificacion=tipo_identificacion,
            identificacion="0990000002",
            empresa=self.empresa,
            es_estudiante=True,
        )
        ficha = FichaInscripcion.objects.create(
            empresa=self.empresa,
            numero="F-001",
            fecha=date(2026, 8, 1),
            cliente=cliente,
            estudiante=estudiante,
            estado="activa",
            activo=True,
        )
        plan = PlanPago.objects.create(
            empresa=self.empresa,
            ficha_inscripcion=ficha,
            valor_total=Decimal("500.00"),
            abono=Decimal("100.00"),
            saldo=Decimal("400.00"),
            estado="activo",
        )
        cuota_atrasada = Cuota.objects.create(
            plan_pago=plan,
            numero=1,
            fecha_pago_debito=date(2026, 8, 1),
            valor=Decimal("250.00"),
            valor_pagado=Decimal("50.00"),
            estado="parcial",
        )
        cuota_proxima = Cuota.objects.create(
            plan_pago=plan,
            numero=2,
            fecha_pago_debito=date(2026, 9, 1),
            valor=Decimal("200.00"),
            valor_pagado=Decimal("0.00"),
            estado="pendiente",
        )
        forma_pago = FormaPago.objects.create(
            empresa=self.empresa,
            nombre="Efectivo",
            tipo="efectivo",
            activo=True,
            es_pago=True,
            orden=1,
        )
        return ficha, plan, cuota_atrasada, cuota_proxima, forma_pago

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
        self.assertContains(response, "instituto-datepicker.css")
        self.assertContains(response, "js-date-picker")

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

    def test_student_pending_payments_page_renders_flow_summary(self):
        self.client.force_login(self.user)
        ficha, _, _, _, _ = self.create_payment_flow_data()

        response = self.client.get(reverse("cartera:alumno_pendientes", kwargs={"pk": ficha.pk}), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_pendiente"], Decimal("400.00"))
        self.assertEqual(response.context["cuotas_pendientes_count"], 2)
        self.assertContains(response, "payment-layout")
        self.assertContains(response, "Cuotas pendientes")
        self.assertContains(response, "Registrar pago")
        self.assertContains(response, "data-payment-modal-list")
        self.assertContains(response, "Fecha registro")

    def test_student_wallet_list_renders_status_filters_and_payment_links(self):
        self.client.force_login(self.user)
        ficha, _, _, _, _ = self.create_payment_flow_data()

        response = self.client.get(reverse("cartera:alumno_cartera_list"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["student_payment_summary"]["pendientes"], 1)
        self.assertEqual(response.context["student_payment_summary"]["vencidos"], 1)
        self.assertContains(response, "Cobros por alumno")
        self.assertContains(response, "Vencidos")
        self.assertContains(response, "Pendientes")
        self.assertContains(response, reverse("cartera:alumno_pendientes", kwargs={"pk": ficha.pk}))

    def test_payment_create_redirects_to_student_wallet_flow(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("cartera:pago_nuevo"), HTTP_HOST="localhost")

        self.assertRedirects(response, reverse("cartera:alumno_cartera_list"), fetch_redirect_response=False)

    def test_student_payment_amount_is_applied_to_overdue_then_next_installment(self):
        self.client.force_login(self.user)
        ficha, plan, cuota_atrasada, cuota_proxima, forma_pago = self.create_payment_flow_data()

        response = self.client.post(
            reverse("cartera:alumno_pendientes", kwargs={"pk": ficha.pk}),
            data={
                "valor": "220.00",
                "forma_pago": forma_pago.pk,
                "fecha_registro": "2026-08-30T10:15",
                "numero_documento": "AB-001",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        cuota_atrasada.refresh_from_db()
        cuota_proxima.refresh_from_db()
        plan.refresh_from_db()
        self.assertEqual(cuota_atrasada.valor_pagado, Decimal("250.00"))
        self.assertEqual(cuota_atrasada.estado, "pagada")
        self.assertEqual(cuota_proxima.valor_pagado, Decimal("20.00"))
        self.assertEqual(cuota_proxima.estado, "parcial")
        self.assertEqual(plan.abono, Decimal("320.00"))
        self.assertEqual(plan.saldo, Decimal("180.00"))
        self.assertEqual(Cuota.objects.get(pk=cuota_atrasada.pk).pagos.first().valor, Decimal("200.00"))
        self.assertEqual(Cuota.objects.get(pk=cuota_proxima.pk).pagos.first().valor, Decimal("20.00"))

    def test_student_payment_receipt_file_uses_student_and_payment_date(self):
        self.client.force_login(self.user)
        ficha, _, cuota_atrasada, _, forma_pago = self.create_payment_flow_data()
        comprobante = SimpleUploadedFile(
            "asistencia_DMEST001.xlsx",
            b"comprobante",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse("cartera:alumno_pendientes", kwargs={"pk": ficha.pk}),
                    data={
                        "cuotas": [cuota_atrasada.pk],
                        "forma_pago": forma_pago.pk,
                        "fecha_registro": "2026-08-30T10:15",
                        "comprobante": comprobante,
                    },
                    HTTP_HOST="localhost",
                )

        self.assertEqual(response.status_code, 302)
        pago = cuota_atrasada.pagos.get()
        self.assertIn("juan-estudiante_20260830_1015_cuota_", pago.comprobante.name)
        self.assertTrue(pago.comprobante.name.endswith(".xlsx"))

    def test_payment_form_renders_date_and_existing_receipt_download(self):
        _, _, cuota_atrasada, _, forma_pago = self.create_payment_flow_data()
        pago = Pago.objects.create(
            empresa=self.empresa,
            cuota=cuota_atrasada,
            forma_pago=forma_pago,
            fecha_registro=timezone.make_aware(datetime(2026, 8, 30, 10, 15)),
            valor=Decimal("10.00"),
            comprobante="cartera/comprobantes/juan-estudiante_20260830_1015_cuota_1.xlsx",
            usuario=self.user,
        )

        html = PagoForm(instance=pago).as_p()

        self.assertIn('value="2026-08-30T10:15"', html)
        self.assertIn("payment-file-link", html)
        self.assertIn("ri-file-excel-2-line", html)
        self.assertIn("Descargar", html)
