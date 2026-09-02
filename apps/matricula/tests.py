import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlparse

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.cartera.models import Cuota, FormaPago
from apps.core.current_user import set_current_request
from apps.core.models import Empresa, Partner, PartnerPartner, TipoIdentificacion

from .forms import MatriculaDatosForm
from .models import Aula, AulaHistorial, Curso, FichaInscripcion, PeriodoAcademico
from .odt import SOFFICE_BIN, SYSTEM_PATH, convert_odt_to_pdf


class ConvertOdtToPdfTests(SimpleTestCase):
    @patch("apps.matricula.odt.subprocess.run")
    @patch("apps.matricula.odt.Path.is_file", return_value=True)
    def test_uses_temporary_libreoffice_profile(self, mock_is_file, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as output_dir:
            odt_path = Path(output_dir) / "ficha.odt"
            result = convert_odt_to_pdf(odt_path, output_dir)

        args = mock_run.call_args.args[0]
        profile_arg = next(arg for arg in args if arg.startswith("-env:UserInstallation="))
        profile_uri = profile_arg.removeprefix("-env:UserInstallation=")
        profile_path = Path(unquote(urlparse(profile_uri).path))

        self.assertEqual(args[0], SOFFICE_BIN)
        self.assertIn("--nofirststartwizard", args)
        self.assertIn("pdf:writer_pdf_Export", args)
        self.assertEqual(mock_run.call_args.kwargs["env"]["HOME"], "/tmp")
        self.assertEqual(mock_run.call_args.kwargs["env"]["PATH"], SYSTEM_PATH)
        self.assertFalse(profile_path.exists())
        self.assertEqual(result.name, "ficha.pdf")

    @patch("apps.matricula.odt.subprocess.run")
    @patch("apps.matricula.odt.Path.is_file", return_value=True)
    def test_raises_conversion_error_with_libreoffice_output(self, mock_is_file, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="fallo real")

        with self.assertRaisesMessage(RuntimeError, "fallo real"):
            convert_odt_to_pdf(Path("/tmp/ficha.odt"), "/tmp")

    @patch("apps.matricula.odt.Path.is_file", return_value=False)
    def test_raises_when_libreoffice_binary_is_missing(self, mock_is_file):
        with self.assertRaisesMessage(RuntimeError, "No se encontró LibreOffice en /usr/bin/soffice."):
            convert_odt_to_pdf(Path("/tmp/ficha.odt"), "/tmp")


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

    def test_process_uses_custom_datepicker_assets(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("matricula:matricula_proceso"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "flatpickr.min.css")
        self.assertContains(response, "instituto-datepicker.css")
        self.assertContains(response, "assets/js/flatpickr.js")
        self.assertContains(response, "js-date-picker")

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
