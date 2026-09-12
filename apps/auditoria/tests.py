from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cartera.models import Cuota, FormaPago, Pago, PlanPago
from apps.core.current_user import get_current_request, set_current_request
from apps.core.models import Empresa, Partner, TipoIdentificacion
from apps.matricula.models import FichaInscripcion

from .models import PagoAuditoria


class PagoAuditoriaTests(TestCase):
    def setUp(self):
        set_current_request(None)
        self.admin_group = Group.objects.get_or_create(name="Administrador")[0]
        self.admin = get_user_model().objects.create_user(
            username="admin_auditoria",
            password="ClaveActual987!",
        )
        self.admin.groups.add(self.admin_group)
        self.editor = get_user_model().objects.create_user(
            username="cajero_auditoria",
            password="ClaveActual987!",
        )
        self.regular_user = get_user_model().objects.create_user(
            username="usuario_sin_auditoria",
            password="ClaveActual987!",
        )
        self.empresa = Empresa.objects.create(
            ruc="1790000000099",
            razon_social="Instituto Auditoría",
            nombre_comercial="Instituto Auditoría",
            activa=True,
        )
        identification_type = TipoIdentificacion.objects.create(nombre="Cédula", codigo="AUD")
        representative = Partner.objects.create(
            empresa=self.empresa,
            tipo_identificacion=identification_type,
            identificacion="AUD-REP-1",
            nombre="Representante Auditoría",
            es_cliente=True,
        )
        self.student = Partner.objects.create(
            empresa=self.empresa,
            tipo_identificacion=identification_type,
            identificacion="AUD-EST-1",
            nombre="Estudiante Auditoría",
            es_estudiante=True,
        )
        self.ficha = FichaInscripcion.objects.create(
            empresa=self.empresa,
            numero="AUD-001",
            fecha=date(2026, 9, 12),
            cliente=representative,
            estudiante=self.student,
            estado="activa",
        )
        self.plan = PlanPago.objects.create(
            empresa=self.empresa,
            ficha_inscripcion=self.ficha,
            valor_total=Decimal("100.00"),
            saldo=Decimal("100.00"),
        )
        self.cuota = Cuota.objects.create(
            plan_pago=self.plan,
            numero=1,
            fecha_pago_debito=date(2026, 10, 12),
            valor=Decimal("100.00"),
        )
        self.forma_pago = FormaPago.objects.create(
            empresa=self.empresa,
            nombre="Transferencia auditoría",
            tipo="transfer_audit",
        )

    def tearDown(self):
        set_current_request(None)

    @staticmethod
    def request_for(user, method="POST", path="/cartera/alumnos/1/pendientes/"):
        return SimpleNamespace(
            user=user,
            method=method,
            path=path,
            META={"REMOTE_ADDR": "127.0.0.25", "HTTP_USER_AGENT": "Audit test"},
        )

    def create_payment(self):
        return Pago.objects.create(
            empresa=self.empresa,
            cuota=self.cuota,
            forma_pago=self.forma_pago,
            fecha_registro=timezone.now(),
            valor=Decimal("50.00"),
            numero_documento="AUD-PAGO-1",
            usuario=self.editor,
            usuario_updated=self.editor,
        )

    def test_payment_creation_records_actor_context_ids_and_snapshot(self):
        set_current_request(self.request_for(self.editor))

        payment = self.create_payment()

        audit = PagoAuditoria.objects.get()
        self.assertEqual(audit.accion, "crear")
        self.assertEqual(audit.pago_id, payment.pk)
        self.assertEqual(audit.empresa_id, self.empresa.pk)
        self.assertEqual(audit.cuota_id, self.cuota.pk)
        self.assertEqual(audit.plan_pago_id, self.plan.pk)
        self.assertEqual(audit.ficha_inscripcion_id, self.ficha.pk)
        self.assertEqual(audit.estudiante_id, self.student.pk)
        self.assertEqual(audit.forma_pago_id, self.forma_pago.pk)
        self.assertEqual(audit.usuario_pago_id, self.editor.pk)
        self.assertEqual(audit.usuario_accion_id, self.editor.pk)
        self.assertEqual(audit.usuario_accion_username, self.editor.username)
        self.assertEqual(audit.ip_address, "127.0.0.25")
        self.assertEqual(audit.metodo_http, "POST")
        self.assertEqual(audit.datos_anteriores, {})
        self.assertEqual(audit.datos_nuevos["valor"], "50.00")

    def test_payment_modification_records_before_after_and_modifying_user(self):
        payment = self.create_payment()
        PagoAuditoria.objects.all().delete()
        set_current_request(self.request_for(self.admin, path=f"/cartera/pagos/{payment.pk}/editar/"))
        payment.valor = Decimal("75.00")
        payment.comentario = "Valor corregido por administración"
        payment.usuario_updated = self.admin

        payment.save(update_fields=["valor", "comentario", "usuario_updated", "updated"])

        audit = PagoAuditoria.objects.get()
        self.assertEqual(audit.accion, "modificar")
        self.assertEqual(audit.usuario_accion_id, self.admin.pk)
        self.assertEqual(audit.datos_anteriores["valor"], "50.00")
        self.assertEqual(audit.datos_nuevos["valor"], "75.00")
        self.assertEqual(
            audit.cambios["valor"],
            {"antes": "50.00", "despues": "75.00"},
        )
        self.assertIn("comentario", audit.cambios)
        self.assertIn("usuario_updated_id", audit.cambios)

    def test_only_administrator_group_or_superuser_can_open_payment_audit(self):
        self.create_payment()
        url = reverse("auditoria:pago_list")
        self.regular_user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="auditoria",
                codename="view_pagoauditoria",
            )
        )

        self.client.force_login(self.regular_user)
        denied_response = self.client.get(url, HTTP_HOST="localhost")

        self.client.force_login(self.admin)
        allowed_response = self.client.get(url, HTTP_HOST="localhost")

        self.assertEqual(denied_response.status_code, 403)
        self.assertEqual(allowed_response.status_code, 200)
        self.assertContains(allowed_response, "Auditoría de pagos")
        self.assertContains(allowed_response, "AUD-PAGO-1")
        self.assertIsNone(get_current_request())
