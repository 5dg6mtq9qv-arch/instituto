import subprocess
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote, urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cartera.models import Cuota, FormaPago, Pago, PlanPago
from apps.core.current_user import set_current_request
from apps.core.models import Empresa, Partner, PartnerPartner, TipoIdentificacion

from .forms import (
    FichaInscripcionForm,
    MatriculaConvenioForm,
    MatriculaDatosForm,
    MatriculaEstudianteForm,
    MatriculaRepresentanteForm,
)
from .models import Aula, AulaHistorial, Curso, FichaInscripcion, PeriodoAcademico
from .odt import SOFFICE_BIN, SYSTEM_PATH, convert_odt_to_pdf, ficha_context, footer_datos, identificacion_numero
from .views import next_ficha_numero


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


class FichaDocumentoContextTests(SimpleTestCase):
    def test_identification_prints_only_digits(self):
        self.assertEqual(identificacion_numero("REP0902045442"), "0902045442")
        self.assertEqual(identificacion_numero("RUC 1790012345001"), "1790012345001")

    def test_william_james_footer_uses_reference_lines(self):
        empresa = SimpleNamespace(
            direccion="Direccion registrada diferente",
            telefono="0989396225",
            ciudad="Ibarra",
        )

        direccion_1, direccion_2, contacto = footer_datos(empresa, "Preuniversitario William James")

        self.assertEqual(
            direccion_1,
            "Av. Carlos Emilio Grijalva entre Juan Genaro Jaramillo y Av. Heleodoro Ayala atrás del nuevo Plásticos y Supermercados San José",
        )
        self.assertEqual(direccion_2, "(a una cuadra de la Academia Superior Militar y Policial ASMIL)")
        self.assertEqual(contacto, "0989396225 / 0978634977   Ibarra - Ecuador")


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

    def create_partner(self, identificacion, nombre, **flags):
        return Partner.objects.create(
            nombre=nombre,
            tipo_identificacion=self.tipo_identificacion,
            identificacion=identificacion,
            empresa=self.empresa,
            **flags,
        )

    def test_student_create_rejects_duplicate_identification(self):
        self.create_partner("1002003001", "Alumno Existente", es_estudiante=True)

        form = MatriculaEstudianteForm(
            data={
                "estudiante_modo": "crear",
                "estudiante_identificacion": "1002003001",
                "estudiante_nombre": "Alumno Nuevo",
                "estudiante_apellido": "Prueba",
            },
            empresa=self.empresa,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Seleccione el estudiante registrado", form.errors["estudiante_identificacion"][0])

    def test_representative_create_rejects_duplicate_identification(self):
        self.create_partner("1002003002", "Representante Existente", es_representante=True)

        form = MatriculaRepresentanteForm(
            data={
                "representante_modo": "crear",
                "representante_identificacion": "1002003002",
                "representante_nombre": "Representante Nuevo",
                "representante_apellido": "Prueba",
            },
            empresa=self.empresa,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Seleccione el representante registrado", form.errors["representante_identificacion"][0])

    def test_process_rejects_same_identification_for_student_and_representative(self):
        self.client.force_login(self.user)
        partner = self.create_partner(
            "1002003009",
            "Persona Duplicada",
            es_cliente=True,
            es_estudiante=True,
            es_representante=True,
        )
        url = reverse("matricula:matricula_proceso")

        response = self.client.post(
            url,
            {
                "estudiante_modo": "seleccionar",
                "estudiante_partner": partner.pk,
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            f"{url}?paso=representante",
            {
                "representante_modo": "seleccionar",
                "representante_partner": partner.pk,
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "La identificacion del representante no puede ser igual a la del estudiante.",
        )

    def test_initial_payment_rejects_duplicate_receipt_number(self):
        cliente = self.create_partner("1002003003", "Maria Representante", es_cliente=True)
        estudiante = self.create_partner("1002003004", "Juan Estudiante", es_estudiante=True)
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
            valor_total=Decimal("100.00"),
            abono=Decimal("0.00"),
            saldo=Decimal("100.00"),
            estado="activo",
        )
        cuota = Cuota.objects.create(
            plan_pago=plan,
            numero=1,
            fecha_pago_debito=date(2026, 9, 1),
            valor=Decimal("100.00"),
            estado="pendiente",
        )
        Pago.objects.create(
            empresa=self.empresa,
            cuota=cuota,
            forma_pago=self.forma_pago,
            fecha_registro=timezone.make_aware(datetime(2026, 8, 30, 10, 15)),
            valor=Decimal("25.00"),
            numero_documento="REC-001",
            usuario=self.user,
        )

        form = MatriculaConvenioForm(
            data={
                "forma_pago_convenio": "mensual",
                "valor_matricula": "25.00",
                "valor_cuota": "50.00",
                "abono": "25.00",
                "forma_pago_abono": self.forma_pago.pk,
                "numero_documento_abono": "rec-001",
                "numero_cuotas": "2",
                "fecha_inicio_cobro": "2026-09-01",
            },
            empresa=self.empresa,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Juan Estudiante", form.errors["numero_documento_abono"][0])

    def test_matricula_data_allows_pending_period_course_and_classroom(self):
        form = MatriculaDatosForm(
            data={
                "numero": "999999",
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
        self.assertTrue(form.fields["numero"].disabled)
        self.assertEqual(form.cleaned_data["numero"], "")
        self.assertEqual(next_ficha_numero(self.empresa), "000001")

    @patch("django.utils.timezone.localdate", return_value=date(2026, 9, 2))
    def test_matricula_data_uses_current_date(self, _mock_localdate):
        form = MatriculaDatosForm(
            data={
                "numero": "999999",
                "fecha": "2026-01-01",
                "colegio": "Colegio Prueba",
                "curso_grado": "Tercero",
                "nota_grado": "9.5",
                "carrera": "Medicina",
                "universidad": "Universidad Central",
            },
            empresa=self.empresa,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.fields["fecha"].disabled)
        self.assertEqual(form.cleaned_data["fecha"], date(2026, 9, 2))

    @patch("django.utils.timezone.localdate", return_value=date(2026, 9, 2))
    def test_process_date_fields_render_current_iso_values(self, _mock_localdate):
        self.client.force_login(self.user)
        url = reverse("matricula:matricula_proceso")
        session = self.client.session
        session["matricula_proceso"] = {
            "matricula": {"fecha": "2026-01-01"},
            "convenio": {"fecha_inicio_cobro": "2026-01-05"},
        }
        session.save()

        response = self.client.get(f"{url}?paso=matricula", HTTP_HOST="localhost")
        self.assertContains(response, 'name="fecha" value="2026-09-02"')

        response = self.client.get(f"{url}?paso=convenio", HTTP_HOST="localhost")
        self.assertContains(response, 'name="fecha_inicio_cobro" value="2026-09-02"')

    def test_ficha_edit_number_is_read_only(self):
        estudiante = self.create_partner("1002003010", "Alumno Uno", es_estudiante=True)
        representante = self.create_partner("1002003011", "Representante Uno", es_cliente=True, es_representante=True)
        ficha = FichaInscripcion.objects.create(
            empresa=self.empresa,
            numero="000001",
            fecha=date(2026, 8, 28),
            cliente=representante,
            estudiante=estudiante,
            representante=representante,
            estado="activa",
            activo=True,
        )

        form = FichaInscripcionForm(instance=ficha)

        self.assertTrue(form.fields["numero"].disabled)
        self.assertEqual(form.fields["numero"].widget.attrs["readonly"], "readonly")

    def test_ficha_edit_locks_payment_fields_when_payments_exist(self):
        estudiante = self.create_partner("1002003012", "Alumno Pago", es_estudiante=True)
        representante = self.create_partner("1002003013", "Representante Pago", es_cliente=True, es_representante=True)
        ficha = FichaInscripcion.objects.create(
            empresa=self.empresa,
            numero="000101",
            fecha=date(2026, 8, 28),
            cliente=representante,
            estudiante=estudiante,
            representante=representante,
            forma_pago_convenio="mensual",
            fecha_proximo_pago=date(2026, 9, 1),
            valor_proximo_pago=Decimal("50.00"),
            abono=Decimal("20.00"),
            saldo=Decimal("80.00"),
            estado="activa",
            activo=True,
        )
        plan = PlanPago.objects.create(
            empresa=self.empresa,
            ficha_inscripcion=ficha,
            valor_total=Decimal("100.00"),
            abono=Decimal("20.00"),
            saldo=Decimal("80.00"),
            estado="activo",
        )
        cuota = Cuota.objects.create(
            plan_pago=plan,
            numero=1,
            fecha_pago_debito=date(2026, 9, 1),
            valor=Decimal("100.00"),
            valor_pagado=Decimal("20.00"),
            estado="parcial",
        )
        Pago.objects.create(
            empresa=self.empresa,
            cuota=cuota,
            forma_pago=self.forma_pago,
            fecha_registro=timezone.make_aware(datetime(2026, 8, 30, 10, 15)),
            valor=Decimal("20.00"),
            numero_documento="REC-LOCK",
            usuario=self.user,
        )

        form = FichaInscripcionForm(instance=ficha)

        self.assertTrue(form.payment_fields_locked)
        for field_name in ["forma_pago_convenio", "fecha_proximo_pago", "valor_proximo_pago", "abono", "saldo"]:
            self.assertTrue(form.fields[field_name].disabled)

    def test_ficha_edit_updates_student_city_switch(self):
        estudiante = self.create_partner("1002003014", "Alumno Ibarra", es_estudiante=True, es_de_ibarra=True)
        representante = self.create_partner("1002003015", "Representante Ibarra", es_cliente=True, es_representante=True)
        ficha = FichaInscripcion.objects.create(
            empresa=self.empresa,
            numero="000102",
            fecha=date(2026, 8, 28),
            cliente=representante,
            estudiante=estudiante,
            representante=representante,
            estado="activa",
            activo=True,
        )
        data = {
            "empresa": self.empresa.pk,
            "numero": ficha.numero,
            "fecha": "2026-08-28",
            "cliente": representante.pk,
            "estudiante": estudiante.pk,
            "representante": representante.pk,
            "edad": "",
            "colegio": "Colegio Prueba",
            "curso_grado": "",
            "nota_grado": "",
            "carrera": "",
            "universidad": "",
            "nombre_conyuge": "",
            "ocupacion_conyuge": "",
            "correo_estudiante": "",
            "correo_representante": "",
            "horario": "",
            "hora": "",
            "duracion": "",
            "forma_pago_convenio": "mensual",
            "fecha_proximo_pago": "",
            "valor_proximo_pago": "0.00",
            "abono": "0.00",
            "saldo": "0.00",
            "estado": "activa",
            "observacion": "",
        }

        form = FichaInscripcionForm(data=data, instance=ficha)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        estudiante.refresh_from_db()
        self.assertFalse(estudiante.es_de_ibarra)

    def test_ficha_list_opens_documents_and_keeps_edit_action(self):
        estudiante = self.create_partner("1002003020", "Alumno Lista", es_estudiante=True)
        representante = self.create_partner("1002003021", "Representante Lista", es_cliente=True, es_representante=True)
        ficha = FichaInscripcion.objects.create(
            empresa=self.empresa,
            numero="000777",
            fecha=date(2026, 8, 28),
            cliente=representante,
            estudiante=estudiante,
            representante=representante,
            estado="activa",
            activo=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("matricula:ficha_list"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("matricula:ficha_documentos", kwargs={"pk": ficha.pk}))
        self.assertContains(response, reverse("matricula:ficha_editar", kwargs={"pk": ficha.pk}))

    def test_ficha_documents_edit_button_requires_change_permission(self):
        estudiante = self.create_partner("1002003022", "Alumno Permiso", es_estudiante=True)
        representante = self.create_partner("1002003023", "Representante Permiso", es_cliente=True, es_representante=True)
        ficha = FichaInscripcion.objects.create(
            empresa=self.empresa,
            numero="000778",
            fecha=date(2026, 8, 28),
            cliente=representante,
            estudiante=estudiante,
            representante=representante,
            estado="activa",
            activo=True,
        )
        view_only = get_user_model().objects.create_user(username="solo_lectura", password="ClaveActual987!")
        view_only.user_permissions.add(Permission.objects.get(codename="view_fichainscripcion"))
        self.client.force_login(view_only)

        response = self.client.get(reverse("matricula:ficha_documentos", kwargs={"pk": ficha.pk}), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("matricula:ficha_editar", kwargs={"pk": ficha.pk}))

    def test_process_uses_custom_datepicker_assets(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("matricula:matricula_proceso"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "flatpickr.min.css")
        self.assertContains(response, "instituto-datepicker.css")
        self.assertContains(response, "assets/js/flatpickr.js")
        self.assertContains(response, "js-date-picker")

    @patch("django.utils.timezone.localdate", return_value=date(2026, 8, 28))
    def test_process_creates_ficha_without_academic_assignment_and_fixed_installments(self, _mock_localdate):
        self.client.force_login(self.user)
        url = reverse("matricula:matricula_proceso")

        response = self.client.post(
            url,
            {
                "estudiante_modo": "crear",
                "estudiante_identificacion": "1002003001",
                "estudiante_nombre": "Alumno Uno",
                "estudiante_apellido": "Prueba",
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
                "representante_apellido": "Prueba",
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
                "numero": "999999",
                "fecha": "2026-08-28",
                "colegio": "Colegio Prueba",
                "estudiante_es_de_ibarra": "on",
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
                "valor_matricula": "80.00",
                "valor_cuota": "50.00",
                "abono": "120.00",
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
        ficha = FichaInscripcion.objects.get(numero="000001")
        self.assertEqual(response["Location"], reverse("matricula:ficha_documentos", kwargs={"pk": ficha.pk}))
        self.assertIsNone(ficha.periodo_academico_id)
        self.assertIsNone(ficha.curso_id)
        self.assertIsNone(ficha.aula_id)
        self.assertEqual(ficha.curso_grado, "Tercero")
        self.assertEqual(ficha.carrera, "Medicina")
        self.assertEqual(ficha.universidad, "Universidad Central")
        self.assertEqual(ficha.valor_proximo_pago, Decimal("10.00"))
        self.assertEqual(ficha.valor_total_curso, Decimal("100.00"))
        self.assertEqual(ficha.valor_matricula, Decimal("80.00"))
        self.assertEqual(ficha.abono, Decimal("120.00"))
        self.assertEqual(ficha.saldo, Decimal("60.00"))
        self.assertEqual(ficha.plan_pago.valor_total, Decimal("180.00"))
        self.assertEqual(ficha.plan_pago.valor_matricula, Decimal("80.00"))
        self.assertEqual(ficha.plan_pago.abono, Decimal("120.00"))

        estudiante = Partner.objects.get(identificacion="1002003001")
        representante = Partner.objects.get(identificacion="1002003002")
        self.assertTrue(estudiante.es_estudiante)
        self.assertTrue(estudiante.es_de_ibarra)
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
        cuota_matricula = Cuota.objects.get(plan_pago=ficha.plan_pago, numero=Cuota.NUMERO_MATRICULA)
        self.assertEqual(cuota_matricula.valor, Decimal("80.00"))
        self.assertEqual(cuota_matricula.valor_pagado, Decimal("80.00"))

        self.assertEqual(cuota_matricula.observacion, "Matricula")
        self.assertEqual(cuota_matricula.pagos.get().comentario, "Pago de matricula")
        primera_cuota = Cuota.objects.get(plan_pago=ficha.plan_pago, numero=1)
        self.assertEqual(primera_cuota.valor, Decimal("50.00"))
        self.assertEqual(primera_cuota.valor_pagado, Decimal("40.00"))
        self.assertEqual(primera_cuota.estado, "parcial")
        self.assertEqual(primera_cuota.pagos.get().valor, Decimal("40.00"))
        self.assertEqual(primera_cuota.pagos.get().comentario, "Abono inicial aplicado a Cuota 1")
        self.assertEqual(Pago.objects.filter(cuota__plan_pago=ficha.plan_pago).count(), 2)
        self.assertEqual(
            list(Cuota.objects.filter(plan_pago=ficha.plan_pago, numero__gt=0).values_list("valor", flat=True)),
            [Decimal("50.00"), Decimal("50.00")],
        )
        document_context = ficha_context(ficha)
        self.assertEqual(document_context["valor_total_curso"], "100.00")
        self.assertEqual(document_context["valor_matricula"], "80.00")
        self.assertEqual(document_context["total"], "180.00")
        self.assertEqual(document_context["abono"], "120.00")
        self.assertEqual(document_context["saldo"], "60.00")
        self.assertEqual(document_context["pago_efectivo"], "X")
        self.assertEqual(
            document_context["cuotas_detalle"],
            [
                {
                    "numero": "Matricula",
                    "fecha": "28/08/2026",
                    "valor": "80.00",
                    "documento": "REC-001",
                    "observacion": "Matricula",
                },
                {
                    "numero": "1",
                    "fecha": "01/09/2026",
                    "valor": "50.00",
                    "documento": "REC-001",
                    "observacion": "Abono inicial aplicado a Cuota 1",
                },
                {
                    "numero": "2",
                    "fecha": "01/10/2026",
                    "valor": "50.00",
                    "documento": "",
                    "observacion": "",
                },
            ],
        )

    def test_matricula_step_saves_student_city_switch_off(self):
        self.client.force_login(self.user)
        url = reverse("matricula:matricula_proceso")

        self.client.post(
            url,
            {
                "estudiante_modo": "crear",
                "estudiante_identificacion": "1002003051",
                "estudiante_nombre": "Alumno Switch",
                "estudiante_apellido": "Prueba",
                "estudiante_fecha_nacimiento": "2008-05-02",
                "estudiante_email": "alumno-switch@example.com",
                "estudiante_telefono": "0991112222",
            },
            HTTP_HOST="localhost",
        )
        self.client.post(
            f"{url}?paso=representante",
            {
                "representante_modo": "crear",
                "representante_identificacion": "1002003052",
                "representante_nombre": "Representante Fuera",
                "representante_apellido": "Prueba",
                "representante_telefono": "062222222",
                "representante_celular": "0993334444",
                "representante_email": "fuera@example.com",
                "representante_ocupacion": "Comerciante",
                "representante_direccion": "Calle 1",
            },
            HTTP_HOST="localhost",
        )
        response = self.client.post(
            f"{url}?paso=matricula",
            {
                "numero": "999999",
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
        estudiante = Partner.objects.get(identificacion="1002003051")
        self.assertFalse(estudiante.es_de_ibarra)
