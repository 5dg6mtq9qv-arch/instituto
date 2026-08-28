from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.cartera.models import Cuota, FormaPago
from apps.core.current_user import set_current_request
from apps.core.models import Empresa, Partner, PartnerPartner, TipoIdentificacion

from .forms import MatriculaDatosForm
from .models import Aula, AulaHistorial, Curso, FichaInscripcion, PeriodoAcademico


class MatriculaProcesoTests(TestCase):
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
        self.tipo_identificacion = TipoIdentificacion.objects.create(nombre="Cedula", codigo="05", activo=True)
        self.periodo = PeriodoAcademico.objects.create(
            empresa=self.empresa,
            nombre="2026-2027",
            estado="activo",
            activo=True,
        )
        self.otro_periodo = PeriodoAcademico.objects.create(
            empresa=self.empresa,
            nombre="2027-2028",
            estado="activo",
            activo=True,
        )
        self.curso = Curso.objects.create(
            empresa=self.empresa,
            nombre="Preuniversitario",
            grado="Admision",
            carrera="Medicina",
            universidad="Universidad Central",
            activo=True,
        )
        self.aula = Aula.objects.create(
            empresa=self.empresa,
            periodo_academico=self.periodo,
            nombre="Beta",
            seccion="A",
            jornada="Nocturna",
            horario="Lunes a viernes",
            hora="18:00 - 20:00",
            duracion="8 semanas",
            capacidad=30,
            activo=True,
        )
        self.aula_otro_periodo = Aula.objects.create(
            empresa=self.empresa,
            periodo_academico=self.otro_periodo,
            nombre="Gamma",
            seccion="B",
            activo=True,
        )
        self.forma_pago = FormaPago.objects.create(
            empresa=self.empresa,
            nombre="Efectivo",
            tipo="efectivo",
            activo=True,
            es_pago=True,
            es_venta=True,
        )

    def tearDown(self):
        set_current_request(None)

    def test_matricula_data_allows_pending_period_course_and_classroom(self):
        form = MatriculaDatosForm(
            data={
                "numero": "0000001",
                "fecha": "2026-08-28",
                "colegio": "Colegio Prueba",
                "curso_grado": "Tercero",
                "nota_grado": "9.5",
                "carrera": "Medicina",
                "universidad": "Universidad Central",
            },
            empresa=self.empresa,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_process_creates_ficha_without_academic_assignment_and_fixed_installments(self):
        self.client.force_login(self.user)
        url = reverse("matricula:matricula_proceso")

        response = self.client.post(
            url,
            {
                "estudiante_modo": "crear",
                "estudiante_identificacion": "1002003001",
                "estudiante_nombre": "Alumno Uno",
                "estudiante_fecha_nacimiento": "2008-05-02",
                "estudiante_email": "alumno@example.com",
                "estudiante_telefono": "0991112222",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{url}?paso=representante")

        response = self.client.post(
            f"{url}?paso=representante",
            {
                "representante_modo": "crear",
                "representante_identificacion": "1002003002",
                "representante_nombre": "Representante Uno",
                "representante_telefono": "062222222",
                "representante_celular": "0993334444",
                "representante_email": "representante@example.com",
                "representante_ocupacion": "Comerciante",
                "representante_direccion": "Calle 1",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{url}?paso=matricula")

        response = self.client.post(
            f"{url}?paso=matricula",
            {
                "numero": "0000001",
                "fecha": "2026-08-28",
                "colegio": "Colegio Prueba",
                "curso_grado": "Tercero",
                "nota_grado": "9.5",
                "carrera": "Medicina",
                "universidad": "Universidad Central",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{url}?paso=convenio")

        response = self.client.post(
            f"{url}?paso=convenio",
            {
                "forma_pago_convenio": "mensual",
                "valor_cuota": "50.00",
                "abono": "30.00",
                "forma_pago_abono": self.forma_pago.pk,
                "numero_documento_abono": "REC-001",
                "numero_cuotas": "2",
                "fecha_inicio_cobro": "2026-09-01",
                "promo": "on",
                "autorizacion_imagen": "on",
                "acepta_garantia": "on",
                "acepta_no_devolucion": "on",
                "observacion": "Matricula de prueba",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        ficha = FichaInscripcion.objects.get(numero="0000001")
        self.assertEqual(response["Location"], reverse("matricula:ficha_documentos", kwargs={"pk": ficha.pk}))
        self.assertIsNone(ficha.periodo_academico_id)
        self.assertIsNone(ficha.curso_id)
        self.assertIsNone(ficha.aula_id)
        self.assertEqual(ficha.curso_grado, "Tercero")
        self.assertEqual(ficha.carrera, "Medicina")
        self.assertEqual(ficha.universidad, "Universidad Central")
        self.assertEqual(ficha.valor_proximo_pago, Decimal("50.00"))
        self.assertEqual(ficha.valor_total_curso, Decimal("130.00"))
        self.assertEqual(ficha.saldo, Decimal("100.00"))

        estudiante = Partner.objects.get(identificacion="1002003001")
        representante = Partner.objects.get(identificacion="1002003002")
        self.assertTrue(estudiante.es_estudiante)
        self.assertTrue(representante.es_cliente)
        self.assertTrue(representante.es_representante)
        self.assertTrue(
            PartnerPartner.objects.filter(
                partner_a=estudiante,
                partner_b=representante,
                relacion="representante",
                principal=True,
                contacto_emergencia=True,
                activo=True,
            ).exists()
        )
        self.assertFalse(AulaHistorial.objects.filter(ficha_inscripcion=ficha).exists())
        self.assertEqual(Cuota.objects.filter(plan_pago=ficha.plan_pago).count(), 3)
        self.assertEqual(
            list(Cuota.objects.filter(plan_pago=ficha.plan_pago, numero__gt=0).values_list("valor", flat=True)),
            [Decimal("50.00"), Decimal("50.00")],
        )
