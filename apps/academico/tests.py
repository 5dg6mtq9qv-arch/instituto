import json
import shutil
import tempfile
from datetime import timedelta, time
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from apps.academico.models import (
    Aula,
    AulaCurso,
    Clase,
    ClaseAsistencia,
    ClaseEstudianteMovimiento,
    ClaseHoraDocente,
    Competencia,
    Curso,
    CursoPeriodo,
    Dia,
    Estrategia,
    GrupoEstudiante,
    Horario,
    HorarioAulaCurso,
    HorarioDia,
    Materia,
    MateriaCurso,
    MoodleConfiguracion,
    MoodleCuenta,
    MoodleCurso,
    MoodleMatricula,
    MateriaSubtema,
    MateriaTema,
    Periodo,
    PlanificacionDocente,
    PlanificacionTema,
    ProfesorMateriaCurso,
    Recurso,
    Subtema,
    Tema,
)
from apps.academico.views import CoordinacionRevisionAsistenciaView, DocenteClaseAsistenciaView
from apps.core.current_user import set_current_request
from apps.core.models import Empresa, Partner, TipoIdentificacion
from apps.matricula.models import FichaInscripcion


class DocenteHorariosPanelTests(TestCase):
    def setUp(self):
        set_current_request(None)
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.user = get_user_model().objects.create_user(username="docente", password="ClaveActual987!")
        self.empresa = Empresa.objects.create(ruc="0999999999001", razon_social="Instituto Prueba")
        self.tipo_identificacion = TipoIdentificacion.objects.create(nombre="Cedula", codigo="CED")
        self.docente = Partner.objects.create(
            tipo_identificacion=self.tipo_identificacion,
            identificacion="DOC-001",
            nombre="Docente Prueba",
            usuario=self.user,
            es_docente=True,
            activo=True,
        )
        self.curso = Curso.objects.create(nombre="Grupo A", activo=True)
        self.aula = Aula.objects.create(nombre="Aula 1")
        aula_curso = AulaCurso.objects.create(aula=self.aula, curso=self.curso)
        dia, _ = Dia.objects.get_or_create(dia="Lunes")
        self.horario = Horario.objects.create(hora_inicio=time(8, 0), hora_fin=time(9, 0))
        horario_dia = HorarioDia.objects.create(dia=dia, horario=self.horario)
        self.horario_aula_curso = HorarioAulaCurso.objects.create(aula_curso=aula_curso, horario_dia=horario_dia)
        self.materia = Materia.objects.create(nombre="Matematicas", nombre_corto="MAT", color="#0f766e")
        self.materia_curso = MateriaCurso.objects.create(materia=self.materia, grupo=self.curso)
        self.profesor_materia_curso = ProfesorMateriaCurso.objects.create(
            partner=self.docente,
            materia_curso=self.materia_curso,
        )
        self.planificacion = PlanificacionDocente.objects.create(
            materia_curso=self.materia_curso,
            nombre="Plan base",
        )
        self.tema = Tema.objects.create(planificacion=self.planificacion, nombre="Numeros", orden=1)
        self.subtema = Subtema.objects.create(tema=self.tema, nombre="Suma", orden=1)
        self.planificacion_tema = PlanificacionTema.objects.create(
            profesor_materia_curso=self.profesor_materia_curso,
            tema=self.tema,
            nombre="Grupo A - Matematicas - Numeros",
        )
        self.competencia = Competencia.objects.create(nombre="Resolver problemas")
        self.estrategia = Estrategia.objects.create(nombre="Aprendizaje guiado")
        self.recurso = Recurso.objects.create(nombre="Pizarra")
        self.competencia.materias.add(self.materia)
        self.estrategia.materias.add(self.materia)
        self.recurso.materias.add(self.materia)
        today = timezone.localdate()
        next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
        self.pendiente = Clase.objects.create(
            horario_aula_curso=self.horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=next_monday,
            estado_planificacion="pendiente",
        )
        self.revision = Clase.objects.create(
            horario_aula_curso=self.horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=next_monday + timedelta(days=7),
            estado_planificacion="revision",
            descripcion="Clase enviada a revision.",
        )
        self.rechazada = Clase.objects.create(
            horario_aula_curso=self.horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=next_monday + timedelta(days=14),
            estado_planificacion="rechazada",
            descripcion="Clase con observaciones.",
            notas_revision="Completar recursos.",
        )
        self.atrasada = Clase.objects.create(
            horario_aula_curso=self.horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=today - timedelta(days=1),
            estado_planificacion="pendiente",
        )

    def tearDown(self):
        set_current_request(None)
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_moodle_permission_and_button_for_coordinator(self):
        user = self.create_coordinator()
        self.assertTrue(user.has_perm("academico.crear_moodlecurso"))
        self.client.force_login(user)
        response = self.client.get(reverse("academico:coordinacion_planificacion_list"), HTTP_HOST="localhost")
        self.assertContains(response, "Crear curso en Moodle")
        user.groups.clear()
        self.client.force_login(user)
        response = self.client.post(reverse("academico:coordinacion_moodle_curso", args=[self.materia_curso.pk]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 403)

    def test_moodle_permission_respects_assigned_subject_restriction(self):
        permission = Permission.objects.get(codename="crear_moodlecurso", content_type__app_label="academico")
        restriction = Permission.objects.get(codename="restrict_to_assigned_materiatema", content_type__app_label="academico")
        self.user.user_permissions.add(permission, restriction)
        other = Materia.objects.create(nombre="Otra materia")
        other_course = MateriaCurso.objects.create(materia=other, grupo=self.curso)
        self.client.force_login(self.user)
        url = reverse("academico:coordinacion_moodle_curso", args=[other_course.pk])
        self.assertEqual(self.client.get(url, HTTP_HOST="localhost").status_code, 404)
        self.assertEqual(self.client.post(url, HTTP_HOST="localhost").status_code, 404)

    def test_moodle_preview_and_missing_students_do_not_call_remote(self):
        from unittest.mock import patch
        MoodleConfiguracion.objects.create(base_url="https://moodle.example")
        MoodleCuenta.objects.create(
            persona=self.docente,
            sitio="https://moodle.example",
            usuario="docente_prueba",
            usuario_id=71,
        )
        self.client.force_login(self.create_coordinator())
        url = reverse("academico:coordinacion_moodle_curso", args=[self.materia_curso.pk])
        with patch("apps.academico.moodle_courses.MoodleClient") as client:
            response = self.client.get(url, HTTP_HOST="localhost")
            self.assertContains(response, "El grupo no tiene alumnos activos matriculados")
            self.assertContains(response, "Usuario existente: docente_prueba")
            self.assertContains(response, "conserva el mismo usuario aunque participe en varias aulas")
            self.assertContains(response, "disabled")
            self.assertContains(response, "Progreso confirmado")
            ajax_response = self.client.post(
                url,
                {"step": "connection"},
                HTTP_HOST="localhost",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(ajax_response.status_code, 400)
            self.assertFalse(ajax_response.json()["retryable"])
            response = self.client.post(url, HTTP_HOST="localhost")
            self.assertEqual(response.status_code, 302)
            client.return_value.site_info.assert_not_called()
            client.return_value.call.assert_not_called()

    def test_moodle_ajax_marks_temporary_errors_for_automatic_retry(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from apps.academico.moodle import MoodleError

        self.client.force_login(self.create_coordinator())
        url = reverse("academico:coordinacion_moodle_curso", args=[self.materia_curso.pk])
        with patch(
            "apps.academico.moodle_courses.sync_moodle_course_step",
            side_effect=MoodleError("Moodle tardó demasiado en responder.", retryable=True),
        ):
            response = self.client.post(
                url,
                {"step": "course"},
                HTTP_HOST="localhost",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(response.json()["retryable"])
        self.assertIn("siguiente intento", response.json()["progress"])

        with patch(
            "apps.academico.moodle_courses.sync_moodle_course_step",
            return_value={
                "link": SimpleNamespace(url="https://moodle.example/course/view.php?id=42"),
                "detail": "Aula creada y confirmada por Moodle con ID 42.",
            },
        ):
            response = self.client.post(
                url,
                {"step": "course"},
                HTTP_HOST="localhost",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["completed_steps"], 2)
        self.assertEqual(response.json()["next_step"], "structure")
        self.assertEqual(response.json()["course_url"], "https://moodle.example/course/view.php?id=42")

    def test_moodle_course_retries_enrolment_without_duplicate_course(self):
        from unittest.mock import patch
        from apps.academico.models import MoodleCurso
        from apps.academico.moodle import MoodleError
        from apps.academico.moodle_courses import create_moodle_course
        data = {"temas": [self.tema], "docentes": [self.docente], "alumnos": [], "errors": []}
        with patch("apps.academico.moodle_courses.course_data", return_value=data), patch("apps.academico.moodle_courses.sync_course_structure"), patch("apps.academico.moodle_courses.MoodleClient") as factory:
            client = factory.return_value
            client.base_url = "https://moodle.example"
            client.missing_functions.return_value = []
            client.call.side_effect = [{"courses": []}, [{"id": 42}]]
            client.users_by_field.return_value = [{"id": 7, "username": "docente_prueba"}]
            self.docente.email = "teacher@example.org"
            client.enrol_users.side_effect = MoodleError("Fallo de matrícula")
            with self.assertRaises(MoodleError):
                create_moodle_course(self.materia_curso)
            link = MoodleCurso.objects.get(materia_curso=self.materia_curso)
            self.assertEqual(link.curso_id, 42)
            self.assertFalse(link.completo)
            client.enrol_users.side_effect = None
            client.enrolled_users.return_value = [{"id": 7}]
            link = create_moodle_course(self.materia_curso)
            self.assertTrue(link.completo)
            self.assertEqual(client.call.call_count, 2)
            create_moodle_course(self.materia_curso)
            self.assertEqual(client.enrol_users.call_count, 1)

    def test_moodle_enrols_only_missing_participants(self):
        from unittest.mock import MagicMock

        from apps.academico.moodle_courses import sync_enrolments

        alumno = Partner.objects.create(
            tipo_identificacion=self.tipo_identificacion,
            identificacion="ALU-MOODLE-001",
            nombre="Alumno Nuevo",
            activo=True,
        )
        link = MoodleCurso.objects.create(
            materia_curso=self.materia_curso,
            sitio="https://moodle.example",
            curso_id=42,
        )
        docente_account = MoodleCuenta.objects.create(
            persona=self.docente,
            sitio=link.sitio,
            usuario="docente_prueba",
            usuario_id=7,
        )
        alumno_account = MoodleCuenta.objects.create(
            persona=alumno,
            sitio=link.sitio,
            usuario="alumno_nuevo",
            usuario_id=8,
        )
        MoodleMatricula.objects.create(
            curso=link,
            cuenta=docente_account,
            rol="Docente",
            confirmada=True,
        )
        MoodleMatricula.objects.create(
            curso=link,
            cuenta=alumno_account,
            rol="Alumno",
        )
        client = MagicMock(base_url=link.sitio)
        client.enrolled_users.side_effect = [[{"id": 7}], [{"id": 7}, {"id": 8}]]

        detail = sync_enrolments(
            client,
            link,
            {"temas": [], "docentes": [self.docente], "alumnos": [alumno], "errors": []},
        )

        client.enrol_users.assert_called_once_with([
            {"roleid": 5, "userid": 8, "courseid": 42}
        ])
        matricula = alumno_account.moodlematricula_set.get(curso=link)
        self.assertTrue(matricula.confirmada)
        link.refresh_from_db()
        self.assertTrue(link.completo)
        self.assertIn("1 matrícula(s) nueva(s)", detail)

    def test_moodle_keeps_partial_progress_and_identifies_rejected_student(self):
        from unittest.mock import MagicMock

        from apps.academico.moodle import MoodleError
        from apps.academico.moodle_courses import sync_enrolments

        alumnos = [
            Partner.objects.create(
                tipo_identificacion=self.tipo_identificacion,
                identificacion=f"ALU-MOODLE-00{number}",
                nombre=name,
                activo=True,
            )
            for number, name in [(2, "Ana Aprobada"), (3, "Beto Rechazado")]
        ]
        link = MoodleCurso.objects.create(
            materia_curso=self.materia_curso,
            sitio="https://moodle.example",
            curso_id=42,
        )
        for user_id, alumno in enumerate(alumnos, start=8):
            account = MoodleCuenta.objects.create(
                persona=alumno,
                sitio=link.sitio,
                usuario=f"alumno_{user_id}",
                usuario_id=user_id,
            )
            MoodleMatricula.objects.create(curso=link, cuenta=account, rol="Alumno")
        client = MagicMock(base_url=link.sitio)
        client.enrolled_users.return_value = []
        client.enrol_users.side_effect = [None, MoodleError("Moodle rechazó la operación.")]

        with self.assertRaisesMessage(MoodleError, "Beto Rechazado"):
            sync_enrolments(
                client,
                link,
                {"temas": [], "docentes": [], "alumnos": alumnos, "errors": []},
            )

        states = dict(
            link.matriculas.values_list("cuenta__persona__nombre", "confirmada")
        )
        self.assertTrue(states["Ana Aprobada"])
        self.assertFalse(states["Beto Rechazado"])
        link.refresh_from_db()
        self.assertFalse(link.completo)

    def test_moodle_recovers_course_after_response_timeout(self):
        from unittest.mock import patch
        from apps.academico.models import MoodleCurso
        from apps.academico.moodle import MoodleError
        from apps.academico.moodle_courses import create_moodle_course
        data = {"temas": [self.tema], "docentes": [], "alumnos": [], "errors": []}
        with patch("apps.academico.moodle_courses.course_data", return_value=data), patch("apps.academico.moodle_courses.sync_course_structure"), patch("apps.academico.moodle_courses.MoodleClient") as factory:
            client = factory.return_value
            client.base_url = "https://moodle.example"
            client.missing_functions.return_value = []
            client.call.side_effect = [{"courses": []}, MoodleError("Tiempo agotado")]
            with self.assertRaises(MoodleError):
                create_moodle_course(self.materia_curso)
            key = MoodleCurso.objects.get(materia_curso=self.materia_curso).clave
            client.call.side_effect = [{"courses": [{"id": 42}]}]
            client.enrolled_users.return_value = []
            link = create_moodle_course(self.materia_curso)
            self.assertEqual(link.clave, key)
            self.assertEqual(link.curso_id, 42)
            self.assertEqual(client.call.call_args.args[0], "core_course_get_courses_by_field")

    def create_coordinator(self):
        user = get_user_model().objects.create_user(username="coordinador", password="ClaveActual987!")
        user.groups.add(Group.objects.get_or_create(name="Coordinacion")[0])
        return user

    def create_director(self):
        user = get_user_model().objects.create_user(username="director", password="ClaveActual987!")
        user.groups.add(Group.objects.get_or_create(name="Director")[0])
        return user

    def create_periodo_for_course(self):
        today = timezone.localdate()
        periodo = Periodo.objects.create(
            nombre="Periodo de prueba",
            fecha_inicio=today,
            fecha_fin=today + timedelta(days=35),
        )
        CursoPeriodo.objects.create(curso=self.curso, periodo=periodo)
        return periodo

    def date_for_weekday(self, periodo, weekday):
        current = periodo.fecha_inicio
        while current <= periodo.fecha_fin:
            if current.weekday() == weekday:
                return current
            current += timedelta(days=1)
        return periodo.fecha_inicio

    def make_superuser(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save(update_fields=["is_staff", "is_superuser"])

    def create_docente(self, username="docente-reemplazo", identificacion="DOC-002", nombre="Docente Reemplazo"):
        user = get_user_model().objects.create_user(username=username, password="ClaveActual987!")
        docente = Partner.objects.create(
            tipo_identificacion=self.tipo_identificacion,
            identificacion=identificacion,
            nombre=nombre,
            usuario=user,
            es_docente=True,
            activo=True,
        )
        return docente, user

    def find_cell_containing(self, sheet, text):
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value and text in str(cell.value):
                    return cell
        self.fail(f"No se encontro una celda con el texto {text!r}")

    def find_cell_containing_all(self, sheet, *texts):
        for row in sheet.iter_rows():
            for cell in row:
                value = str(cell.value or "")
                if all(text in value for text in texts):
                    return cell
        self.fail(f"No se encontro una celda con los textos {texts!r}")

    def create_class_for_date(
        self,
        fecha,
        hora_inicio,
        hora_fin,
        aula_nombre="Aula extra",
        materia_curso=None,
        curso=None,
    ):
        curso = curso or self.curso
        aula = Aula.objects.create(nombre=aula_nombre)
        aula_curso = AulaCurso.objects.create(aula=aula, curso=curso)
        weekday_names = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        dia, _ = Dia.objects.get_or_create(dia=weekday_names[fecha.weekday()])
        horario, _ = Horario.objects.get_or_create(hora_inicio=hora_inicio, hora_fin=hora_fin)
        horario_dia, _ = HorarioDia.objects.get_or_create(dia=dia, horario=horario)
        horario_aula_curso = HorarioAulaCurso.objects.create(aula_curso=aula_curso, horario_dia=horario_dia)
        return Clase.objects.create(
            horario_aula_curso=horario_aula_curso,
            materia_curso=materia_curso or self.materia_curso,
            fecha=fecha,
        )

    def create_student_ficha(
        self,
        nombre="Estudiante Prueba",
        identificacion="EST-001",
        numero="F-001",
        apellido="",
        activo=True,
        es_de_ibarra=True,
    ):
        estudiante = Partner.objects.create(
            tipo_identificacion=self.tipo_identificacion,
            identificacion=identificacion,
            nombre=nombre,
            apellido=apellido,
            es_estudiante=True,
            activo=activo,
            es_de_ibarra=es_de_ibarra,
        )
        representante = Partner.objects.create(
            tipo_identificacion=self.tipo_identificacion,
            identificacion=f"REP-{identificacion}",
            nombre=f"Representante {nombre}",
            es_representante=True,
            activo=True,
        )
        ficha = FichaInscripcion.objects.create(
            empresa=self.empresa,
            numero=numero,
            fecha=timezone.localdate(),
            cliente=representante,
            estudiante=estudiante,
            representante=representante,
            estado="activa",
            activo=True,
        )
        return estudiante, ficha

    def test_group_student_selector_orders_by_last_name_and_exposes_full_filters(self):
        self.make_superuser()
        estudiante_zuniga, ficha_zuniga = self.create_student_ficha(
            nombre="Juan",
            apellido="Zúñiga",
            identificacion="EST-FILTER-1",
            numero="F-FILTER-1",
        )
        estudiante_alvarez, ficha_alvarez = self.create_student_ficha(
            nombre="Ana",
            apellido="Álvarez",
            identificacion="EST-FILTER-2",
            numero="F-FILTER-2",
            activo=False,
            es_de_ibarra=False,
        )
        estudiante_zamora, ficha_zamora = self.create_student_ficha(
            nombre="Pedro",
            apellido="Zamora",
            identificacion="EST-FILTER-3",
            numero="F-FILTER-3",
        )
        estudiante_acosta, ficha_acosta = self.create_student_ficha(
            nombre="Beatriz",
            apellido="Acosta",
            identificacion="EST-FILTER-4",
            numero="F-FILTER-4",
            es_de_ibarra=False,
        )
        estudiante_alvarez.email = "ana.filtro@example.com"
        estudiante_alvarez.telefono_celular = "0991234567"
        estudiante_alvarez.save(update_fields=["email", "telefono_celular"])
        ficha_alvarez.carrera = "Medicina"
        ficha_alvarez.save(update_fields=["carrera"])
        GrupoEstudiante.objects.create(ficha_inscripcion=ficha_zamora, estudiante=estudiante_zamora, grupo=self.curso)
        GrupoEstudiante.objects.create(ficha_inscripcion=ficha_acosta, estudiante=estudiante_acosta, grupo=self.curso)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:grupo_estudiantes"),
            {"grupo": self.curso.pk},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["display_name"] for row in response.context["available_students"]],
            ["Zúñiga Juan"],
        )
        self.assertEqual(
            [row["display_name"] for row in response.context["assigned_students"]],
            ["Acosta Beatriz", "Zamora Pedro"],
        )
        self.assertNotContains(response, "Álvarez Ana")
        self.assertContains(response, 'data-transfer-filter="ibarra"')
        self.assertContains(response, "Buscar en todos los campos", count=2)
        self.assertContains(response, 'data-ibarra="no"')

    def test_group_student_assignment_view_creates_academic_group_assignment(self):
        self.make_superuser()
        estudiante, ficha = self.create_student_ficha()
        self.client.force_login(self.user)

        page_response = self.client.get(reverse("academico:grupo_estudiantes"), HTTP_HOST="localhost")

        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, "student-transfer-board")
        self.assertContains(page_response, "data-transfer-action=\"assign\"")

        response = self.client.post(
            reverse("academico:grupo_estudiantes"),
            {
                "assignment_action": "sync_students",
                "grupo": self.curso.pk,
                "fecha_asignacion": timezone.localdate().isoformat(),
                "fichas": [ficha.pk],
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        asignacion = GrupoEstudiante.objects.get(ficha_inscripcion=ficha)
        self.assertEqual(asignacion.estudiante, estudiante)
        self.assertEqual(asignacion.grupo, self.curso)
        self.assertEqual(asignacion.estado, "activo")

    def test_group_student_assignment_view_can_return_student_to_unassigned(self):
        self.make_superuser()
        estudiante, ficha = self.create_student_ficha()
        asignacion = GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha,
            estudiante=estudiante,
            grupo=self.curso,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:grupo_estudiantes"),
            {
                "assignment_action": "sync_students",
                "grupo": self.curso.pk,
                "fecha_asignacion": timezone.localdate().isoformat(),
                "asignaciones_remover": [asignacion.pk],
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        asignacion.refresh_from_db()
        self.assertEqual(asignacion.estado, "retirado")
        self.assertEqual(asignacion.fecha_fin, timezone.localdate())

    def test_period_close_preserves_history_and_allows_same_ficha_in_next_period(self):
        self.make_superuser()
        today = timezone.localdate()
        current_period = Periodo.objects.create(
            nombre="Nivelacion",
            fecha_inicio=today - timedelta(days=30),
            fecha_fin=today,
        )
        CursoPeriodo.objects.create(curso=self.curso, periodo=current_period)
        estudiante, ficha = self.create_student_ficha(
            nombre="Maria",
            apellido="Especializacion",
            identificacion="EST-PROMOTION",
            numero="F-PROMOTION",
        )
        previous_assignment = GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha,
            estudiante=estudiante,
            grupo=self.curso,
            periodo=current_period,
            fecha_asignacion=current_period.fecha_inicio,
        )
        historical_class = self.create_class_for_date(
            today,
            time(13, 0),
            time(14, 0),
            "Aula nivelacion",
        )
        self.client.force_login(self.user)

        period_page = self.client.get(reverse("academico:periodo_list"), HTTP_HOST="localhost")
        self.assertContains(period_page, "sweetalert2@11")
        self.assertContains(period_page, "data-period-close-form")
        self.assertNotContains(period_page, "return confirm(")

        close_response = self.client.post(
            reverse("academico:periodo_cerrar", args=[current_period.pk]),
            HTTP_HOST="localhost",
        )
        current_period.refresh_from_db()
        previous_assignment.refresh_from_db()

        self.assertEqual(close_response.status_code, 302)
        self.assertEqual(current_period.estado, "cerrado")
        self.assertEqual(previous_assignment.estado, "finalizado")
        self.assertEqual(previous_assignment.fecha_fin, current_period.fecha_fin)
        historical_rows, _ = DocenteClaseAsistenciaView().get_roster_rows(historical_class)
        self.assertEqual([row["estudiante"] for row in historical_rows], [estudiante])

        next_period = Periodo.objects.create(
            nombre="Especializacion",
            fecha_inicio=today + timedelta(days=1),
            fecha_fin=today + timedelta(days=120),
        )
        specialization_group = Curso.objects.create(nombre="Contabilidad A", activo=True)
        CursoPeriodo.objects.create(curso=specialization_group, periodo=next_period)

        page_response = self.client.get(
            reverse("academico:grupo_estudiantes"),
            {"grupo": specialization_group.pk},
            HTTP_HOST="localhost",
        )
        self.assertIn(ficha, page_response.context["available_fichas"])

        assign_response = self.client.post(
            reverse("academico:grupo_estudiantes"),
            {
                "assignment_action": "sync_students",
                "grupo": specialization_group.pk,
                "fecha_asignacion": next_period.fecha_inicio.isoformat(),
                "fichas": [ficha.pk],
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(assign_response.status_code, 302)
        assignments = GrupoEstudiante.objects.filter(ficha_inscripcion=ficha).order_by("periodo__fecha_inicio")
        self.assertEqual(assignments.count(), 2)
        self.assertEqual(assignments[0].pk, previous_assignment.pk)
        self.assertEqual(assignments[0].estado, "finalizado")
        self.assertEqual(assignments[1].periodo, next_period)
        self.assertEqual(assignments[1].grupo, specialization_group)
        self.assertEqual(assignments[1].estado, "activo")

    def test_period_close_requires_dedicated_permission(self):
        today = timezone.localdate()
        period = Periodo.objects.create(
            nombre="Periodo protegido",
            fecha_inicio=today,
            fecha_fin=today + timedelta(days=30),
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename="view_periodo", content_type__app_label="academico"),
            Permission.objects.get(codename="change_periodo", content_type__app_label="academico"),
        )
        self.client.force_login(self.user)

        page_without_permission = self.client.get(
            reverse("academico:periodo_list"),
            HTTP_HOST="localhost",
        )
        close_without_permission = self.client.post(
            reverse("academico:periodo_cerrar", args=[period.pk]),
            HTTP_HOST="localhost",
        )
        period.refresh_from_db()

        self.assertNotContains(page_without_permission, "data-period-close-form")
        self.assertEqual(close_without_permission.status_code, 403)
        self.assertEqual(period.estado, "activo")

        self.user.user_permissions.add(
            Permission.objects.get(codename="close_periodo", content_type__app_label="academico")
        )
        self.client.force_login(self.user)
        page_with_permission = self.client.get(
            reverse("academico:periodo_list"),
            HTTP_HOST="localhost",
        )
        close_with_permission = self.client.post(
            reverse("academico:periodo_cerrar", args=[period.pk]),
            HTTP_HOST="localhost",
        )
        period.refresh_from_db()

        self.assertContains(page_with_permission, "data-period-close-form")
        self.assertEqual(close_with_permission.status_code, 302)
        self.assertEqual(period.estado, "cerrado")

    def test_group_assignment_is_default_roster_for_all_group_classes(self):
        today = timezone.localdate()
        first_class = self.create_class_for_date(today, time(10, 0), time(11, 0), "Aula asistencia 1")
        second_class = self.create_class_for_date(today, time(11, 0), time(12, 0), "Aula asistencia 2")
        estudiante, ficha = self.create_student_ficha()
        GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha,
            estudiante=estudiante,
            grupo=self.curso,
        )
        self.client.force_login(self.user)

        first_response = self.client.get(
            reverse("academico:docente_clase_asistencia", args=[first_class.pk]),
            HTTP_HOST="localhost",
        )
        second_response = self.client.get(
            reverse("academico:docente_clase_asistencia", args=[second_class.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual([row["estudiante"] for row in first_response.context["rows"]], [estudiante])
        self.assertEqual([row["estudiante"] for row in second_response.context["rows"]], [estudiante])
        self.assertFalse(ClaseAsistencia.objects.filter(estudiante=estudiante).exists())

    def test_students_assigned_after_class_date_do_not_create_pending_attendance(self):
        today = timezone.localdate()
        past_date = today - timedelta(days=7)
        past_class = self.create_class_for_date(
            past_date,
            time(10, 0),
            time(11, 0),
            "Aula asistencia historica",
        )
        previous_student, previous_ficha = self.create_student_ficha(
            nombre="Alumno Anterior",
            identificacion="EST-HISTORY-1",
            numero="F-HISTORY-1",
        )
        new_student, new_ficha = self.create_student_ficha(
            nombre="Alumno Nuevo",
            identificacion="EST-HISTORY-2",
            numero="F-HISTORY-2",
        )
        GrupoEstudiante.objects.create(
            ficha_inscripcion=previous_ficha,
            estudiante=previous_student,
            grupo=self.curso,
            fecha_asignacion=past_date,
        )
        GrupoEstudiante.objects.create(
            ficha_inscripcion=new_ficha,
            estudiante=new_student,
            grupo=self.curso,
            fecha_asignacion=today,
        )
        ClaseAsistencia.objects.create(
            clase=past_class,
            estudiante=previous_student,
            estado="presente",
            registrado_por=self.docente,
        )

        view = CoordinacionRevisionAsistenciaView()
        roster_data = view.get_roster_data([past_class])
        card = view.build_attendance_card(past_class, roster_data=roster_data)

        self.assertEqual(card["total_estudiantes"], 1)
        self.assertEqual(card["saved_count"], 1)
        self.assertEqual(card["pending_count"], 0)
        self.assertEqual([row["estudiante"] for row in card["fichas"]], [previous_student])

    def test_student_assigned_after_same_day_closure_does_not_create_pending_attendance(self):
        today = timezone.localdate()
        clase = self.create_class_for_date(
            today,
            time(10, 0),
            time(11, 0),
            "Aula cierre antes de matricula",
        )
        clase.asistencia_cerrada = True
        clase.fecha_cierre_asistencia = timezone.now()
        clase.save(update_fields=["asistencia_cerrada", "fecha_cierre_asistencia"])
        estudiante, ficha = self.create_student_ficha(
            nombre="Alumno Posterior Al Cierre",
            identificacion="EST-AFTER-CLOSE",
            numero="F-AFTER-CLOSE",
        )
        asignacion = GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha,
            estudiante=estudiante,
            grupo=self.curso,
            fecha_asignacion=today,
        )
        self.assertGreater(asignacion.created_at, clase.fecha_cierre_asistencia)

        view = CoordinacionRevisionAsistenciaView()
        roster_data = view.get_roster_data([clase])
        card = view.build_attendance_card(clase, roster_data=roster_data)

        self.assertEqual(card["total_estudiantes"], 0)
        self.assertEqual(card["saved_count"], 0)
        self.assertEqual(card["pending_count"], 0)

    def test_inactive_student_is_hidden_from_group_and_class_operational_lists(self):
        self.make_superuser()
        estudiante, ficha = self.create_student_ficha(activo=False)
        asignacion = GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha,
            estudiante=estudiante,
            grupo=self.curso,
        )
        clase = self.create_class_for_date(
            timezone.localdate(),
            time(10, 0),
            time(11, 0),
            "Aula estudiante inactivo",
        )
        self.client.force_login(self.user)

        group_response = self.client.get(
            reverse("academico:grupo_estudiantes"),
            {"grupo": self.curso.pk},
            HTTP_HOST="localhost",
        )
        attendance_response = self.client.get(
            reverse("academico:docente_clase_asistencia", args=[clase.pk]),
            HTTP_HOST="localhost",
        )

        self.assertTrue(GrupoEstudiante.objects.filter(pk=asignacion.pk).exists())
        self.assertNotIn(estudiante, [row["ficha"].estudiante for row in group_response.context["assigned_students"]])
        self.assertNotIn(estudiante, [row["ficha"].estudiante for row in group_response.context["available_students"]])
        self.assertNotIn(estudiante, list(group_response.context["movement_form"].fields["asignacion"].queryset))
        self.assertEqual(group_response.context["stats"]["asignados"], 0)
        self.assertNotIn(estudiante, [row["estudiante"] for row in attendance_response.context["rows"]])

    def test_docente_can_view_but_not_edit_attendance_outside_class_date(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_clase_asistencia", args=[self.pendiente.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_edit_attendance"])

        response = self.client.post(
            reverse("academico:docente_clase_asistencia", args=[self.pendiente.pk]),
            {"attendance_action": "save"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("academico:docente_asistencias"))

    def test_class_student_movement_requires_same_materia_in_another_group(self):
        estudiante, ficha = self.create_student_ficha()
        asignacion = GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha,
            estudiante=estudiante,
            grupo=self.curso,
        )
        grupo_destino = Curso.objects.create(nombre="Grupo B", activo=True)
        materia_curso_destino = MateriaCurso.objects.create(materia=self.materia, grupo=grupo_destino)
        target_class = self.create_class_for_date(
            self.pendiente.fecha,
            time(10, 0),
            time(11, 0),
            "Aula destino",
            materia_curso=materia_curso_destino,
            curso=grupo_destino,
        )
        valid_movement = ClaseEstudianteMovimiento(
            asignacion=asignacion,
            clase_origen=self.pendiente,
            clase_destino=target_class,
        )

        valid_movement.full_clean()

        same_group_movement = ClaseEstudianteMovimiento(
            asignacion=asignacion,
            clase_origen=self.pendiente,
            clase_destino=self.revision,
        )
        with self.assertRaises(ValidationError) as same_group_error:
            same_group_movement.full_clean()

        self.assertIn(
            "Selecciona una clase destino de otro grupo.",
            same_group_error.exception.message_dict["clase_destino"],
        )

        otra_materia = Materia.objects.create(nombre="Lenguaje", nombre_corto="LEN", color="#2563eb")
        otra_materia_curso = MateriaCurso.objects.create(materia=otra_materia, grupo=grupo_destino)
        wrong_class = self.create_class_for_date(
            self.pendiente.fecha + timedelta(days=1),
            time(11, 0),
            time(12, 0),
            "Aula materia distinta",
            materia_curso=otra_materia_curso,
            curso=grupo_destino,
        )
        invalid_movement = ClaseEstudianteMovimiento(
            asignacion=asignacion,
            clase_origen=self.pendiente,
            clase_destino=wrong_class,
        )

        with self.assertRaises(ValidationError) as error:
            invalid_movement.full_clean()

        self.assertIn(
            "Solo puedes mover entre grupos que tengan la misma materia.",
            error.exception.message_dict["clase_destino"],
        )

    def test_group_student_movement_view_changes_subject_to_equivalent_group(self):
        self.make_superuser()
        today = timezone.localdate()
        estudiante, ficha = self.create_student_ficha()
        asignacion = GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha,
            estudiante=estudiante,
            grupo=self.curso,
        )
        grupo_destino = Curso.objects.create(nombre="Grupo B", activo=True)
        materia_curso_destino = MateriaCurso.objects.create(materia=self.materia, grupo=grupo_destino)
        origin_class = self.create_class_for_date(today, time(10, 0), time(11, 0), "Aula origen movimiento")
        destination_class = self.create_class_for_date(
            today,
            time(12, 0),
            time(13, 0),
            "Aula destino movimiento",
            materia_curso=materia_curso_destino,
            curso=grupo_destino,
        )
        self.client.force_login(self.user)

        page_response = self.client.get(
            reverse("academico:grupo_estudiantes"),
            {"grupo": self.curso.pk},
            HTTP_HOST="localhost",
        )

        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, "id_materia_origen")
        self.assertContains(page_response, "id_materia_destino")
        self.assertNotContains(page_response, "id_clase_origen")

        response = self.client.post(
            reverse("academico:grupo_estudiantes"),
            {
                "assignment_action": "move_student",
                "grupo": self.curso.pk,
                "asignacion": asignacion.pk,
                "materia_origen": self.materia_curso.pk,
                "materia_destino": materia_curso_destino.pk,
                "fecha_inicio": today.isoformat(),
                "motivo": "Cambio de horario.",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        movimiento = ClaseEstudianteMovimiento.objects.get(asignacion=asignacion)
        self.assertEqual(movimiento.clase_origen, origin_class)
        self.assertEqual(movimiento.clase_destino, destination_class)
        self.assertEqual(movimiento.fecha_inicio, today)
        self.assertEqual(movimiento.motivo, "Cambio de horario.")
        self.assertEqual(asignacion.grupo, self.curso)

    def test_docente_attendance_uses_group_roster_and_movement_exceptions(self):
        today = timezone.localdate()
        origin_class = self.create_class_for_date(today, time(10, 0), time(11, 0), "Aula origen")
        grupo_destino = Curso.objects.create(nombre="Grupo B", activo=True)
        materia_curso_destino = MateriaCurso.objects.create(materia=self.materia, grupo=grupo_destino)
        ProfesorMateriaCurso.objects.create(partner=self.docente, materia_curso=materia_curso_destino)
        destination_class = self.create_class_for_date(
            today,
            time(11, 0),
            time(12, 0),
            "Aula destino",
            materia_curso=materia_curso_destino,
            curso=grupo_destino,
        )
        future_origin_class = self.create_class_for_date(
            today + timedelta(days=7),
            time(10, 0),
            time(11, 0),
            "Aula origen futura",
        )
        future_destination_class = self.create_class_for_date(
            today + timedelta(days=7),
            time(11, 0),
            time(12, 0),
            "Aula destino futura",
            materia_curso=materia_curso_destino,
            curso=grupo_destino,
        )
        estudiante_uno, ficha_uno = self.create_student_ficha(
            nombre="Ana Estudiante",
            identificacion="EST-101",
            numero="F-101",
        )
        estudiante_dos, ficha_dos = self.create_student_ficha(
            nombre="Luis Estudiante",
            identificacion="EST-102",
            numero="F-102",
        )
        asignacion_uno = GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha_uno,
            estudiante=estudiante_uno,
            grupo=self.curso,
        )
        asignacion_dos = GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha_dos,
            estudiante=estudiante_dos,
            grupo=self.curso,
        )
        ClaseEstudianteMovimiento.objects.create(
            asignacion=asignacion_dos,
            clase_origen=origin_class,
            clase_destino=destination_class,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_clase_asistencia", args=[origin_class.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "attendance-status-group")
        self.assertEqual([row["estudiante"] for row in response.context["rows"]], [estudiante_uno])
        self.assertEqual(response.context["moved_out_rows"][0]["estudiante"], estudiante_dos)

        response = self.client.post(
            reverse("academico:docente_clase_asistencia", args=[origin_class.pk]),
            {
                f"estado_{asignacion_uno.pk}": "ausente",
                f"observacion_{asignacion_uno.pk}": "No asistio.",
                f"estado_{asignacion_dos.pk}": "presente",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        asistencia = ClaseAsistencia.objects.get(clase=origin_class, estudiante=estudiante_uno)
        self.assertEqual(asistencia.estado, "ausente")
        self.assertEqual(asistencia.observacion, "No asistio.")
        self.assertFalse(ClaseAsistencia.objects.filter(clase=origin_class, estudiante=estudiante_dos).exists())

        destination_response = self.client.get(
            reverse("academico:docente_clase_asistencia", args=[destination_class.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(destination_response.status_code, 200)
        self.assertEqual(len(destination_response.context["rows"]), 1)
        incoming_rows = [row for row in destination_response.context["rows"] if row["incoming"]]
        self.assertEqual(incoming_rows[0]["estudiante"], estudiante_dos)

        roster_view = DocenteClaseAsistenciaView()
        future_origin_rows, future_origin_moved_out = roster_view.get_roster_rows(future_origin_class)
        future_destination_rows, _ = roster_view.get_roster_rows(future_destination_class)

        self.assertEqual([row["estudiante"] for row in future_origin_rows], [estudiante_uno])
        self.assertEqual(future_origin_moved_out[0]["estudiante"], estudiante_dos)
        self.assertEqual([row["estudiante"] for row in future_destination_rows], [estudiante_dos])
        self.assertTrue(future_destination_rows[0]["incoming"])

    def test_docente_can_close_attendance_after_save_and_lock_changes(self):
        today_class = self.create_class_for_date(timezone.localdate(), time(10, 0), time(11, 0), "Aula cierre")
        estudiante, ficha = self.create_student_ficha()
        asignacion = GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha,
            estudiante=estudiante,
            grupo=self.curso,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_clase_asistencia", args=[today_class.pk]),
            {
                "attendance_action": "save",
                f"estado_{asignacion.pk}": "presente",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        page_response = self.client.get(
            reverse("academico:docente_clase_asistencia", args=[today_class.pk]),
            HTTP_HOST="localhost",
        )
        self.assertContains(page_response, "Cerrar asistencia")

        response = self.client.post(
            reverse("academico:docente_clase_asistencia", args=[today_class.pk]),
            {"attendance_action": "close"},
            HTTP_HOST="localhost",
        )
        today_class.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(today_class.asistencia_cerrada)
        self.assertEqual(today_class.asistencia_cerrada_por, self.docente)
        self.assertIsNotNone(today_class.fecha_cierre_asistencia)

        response = self.client.post(
            reverse("academico:docente_clase_asistencia", args=[today_class.pk]),
            {
                "attendance_action": "save",
                f"estado_{asignacion.pk}": "ausente",
            },
            HTTP_HOST="localhost",
        )
        asistencia = ClaseAsistencia.objects.get(clase=today_class, estudiante=estudiante)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(asistencia.estado, "presente")
        locked_response = self.client.get(
            reverse("academico:docente_clase_asistencia", args=[today_class.pk]),
            HTTP_HOST="localhost",
        )
        self.assertContains(locked_response, "Asistencia cerrada")
        self.assertContains(locked_response, "Registro bloqueado")

    def test_docente_dashboard_renders_panel_cards(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("academico:docente_horarios"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mis planificaciones")
        self.assertContains(response, "Por atender")
        self.assertContains(response, "docente-planning-card")
        self.assertEqual(response.context["planificacion_stats"]["total"], 4)
        self.assertEqual(response.context["planificacion_stats"]["por_atender"], 3)

    def test_docente_attendance_panel_separates_pending_and_taken_classes(self):
        today = timezone.localdate()
        today_class = self.create_class_for_date(today, time(10, 0), time(11, 0), "Aula asistencia hoy")
        closed_class = self.create_class_for_date(
            today - timedelta(days=7),
            time(10, 0),
            time(11, 0),
            "Aula asistencia cerrada",
        )
        estudiante, ficha = self.create_student_ficha()
        GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha,
            estudiante=estudiante,
            grupo=self.curso,
        )
        ClaseAsistencia.objects.create(
            clase=closed_class,
            estudiante=estudiante,
            estado="presente",
            registrado_por=self.docente,
        )
        closed_class.asistencia_cerrada = True
        closed_class.asistencia_cerrada_por = self.docente
        closed_class.fecha_cierre_asistencia = timezone.now()
        closed_class.save(
            update_fields=["asistencia_cerrada", "asistencia_cerrada_por", "fecha_cierre_asistencia"]
        )
        self.user.groups.add(Group.objects.get_or_create(name="Docente")[0])
        self.user.groups.add(Group.objects.get_or_create(name="Coordinacion")[0])
        self.client.force_login(self.user)

        pending_response = self.client.get(
            reverse("academico:docente_asistencias"),
            HTTP_HOST="localhost",
        )

        self.assertEqual(pending_response.status_code, 200)
        self.assertEqual(pending_response.context["selected_status"], "pendientes")
        self.assertEqual(pending_response.context["pending_count"], 1)
        self.assertEqual(pending_response.context["taken_count"], 1)
        self.assertEqual(
            [card["clase"] for card in pending_response.context["attendance_cards"]],
            [today_class],
        )
        self.assertContains(pending_response, "Tomar asistencia")

        taken_response = self.client.get(
            reverse("academico:docente_asistencias"),
            {"estado": "tomadas"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(taken_response.status_code, 200)
        self.assertEqual(taken_response.context["selected_status"], "tomadas")
        self.assertEqual(
            [card["clase"] for card in taken_response.context["attendance_cards"]],
            [closed_class],
        )
        self.assertContains(taken_response, "Ver asistencia")

        history_response = self.client.get(
            reverse("academico:docente_clase_asistencia", args=[closed_class.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(history_response.status_code, 200)
        self.assertContains(history_response, "Asistencia cerrada")
        self.assertContains(history_response, "Registro bloqueado")

    def test_docente_dashboard_shows_assigned_subject_without_topics(self):
        materia = Materia.objects.create(nombre="Lenguaje", nombre_corto="LEN", color="#2563eb")
        materia_curso = MateriaCurso.objects.create(materia=materia, grupo=self.curso)
        ProfesorMateriaCurso.objects.create(partner=self.docente, materia_curso=materia_curso)
        self.client.force_login(self.user)

        response = self.client.get(reverse("academico:docente_horarios"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Materias asignadas")
        self.assertContains(response, "Lenguaje")
        self.assertContains(response, "Completa el temario para acceder a las planificaciones.")
        card = next(card for card in response.context["materia_cards"] if card["materia"] == materia)
        self.assertFalse(card["has_topics"])
        self.assertEqual(card["tema_cards"], [])
        self.assertContains(response, "Abrir planificacion")

    def test_docente_dashboard_groups_planifications_by_topic(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("academico:docente_horarios"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planificaciones por tema")
        self.assertContains(response, self.tema.nombre)
        self.assertEqual(len(response.context["tema_cards"]), 1)
        self.assertEqual(response.context["tema_cards"][0]["tema"], self.tema)
        self.assertEqual(response.context["tema_cards"][0]["available_count"], 3)

    def test_docente_dashboard_filters_by_own_group(self):
        grupo = Curso.objects.create(nombre="Grupo B", activo=True)
        materia = Materia.objects.create(nombre="Lenguaje grupo B", nombre_corto="LB")
        asignacion = MateriaCurso.objects.create(grupo=grupo, materia=materia)
        ProfesorMateriaCurso.objects.create(partner=self.docente, materia_curso=asignacion)
        ajeno = Curso.objects.create(nombre="Grupo ajeno", activo=True)
        MateriaCurso.objects.create(grupo=ajeno, materia=materia)
        self.client.force_login(self.user)
        url = reverse("academico:docente_horarios")
        response = self.client.get(url, {"grupo": grupo.pk}, HTTP_HOST="localhost")
        self.assertEqual(response.context["grupos"], [self.curso, grupo])
        self.assertEqual(response.context["selected_grupo"], grupo)
        self.assertEqual([card["materia"] for card in response.context["materia_cards"]], [materia])
        self.assertEqual(response.context["planificacion_stats"]["total"], 0)
        self.assertEqual(response.context["tema_cards"], [])
        self.assertNotContains(response, "Grupo ajeno")
        for tab in response.context["status_tabs"]:
            self.assertIn(f"grupo={grupo.pk}", tab["url"])
        response = self.client.get(url, {"grupo": self.curso.pk, "estado": "trabajo"}, HTTP_HOST="localhost")
        self.assertEqual(response.context["planificacion_stats"]["total"], 4)
        self.assertNotContains(response, "Lenguaje grupo B")
        response = self.client.get(url, {"grupo": ajeno.pk}, HTTP_HOST="localhost")
        self.assertEqual(response.context["selected_grupo"], self.curso)

    def test_docente_dashboard_temario_link_requires_edit_permission(self):
        materia = Materia.objects.create(nombre="Sin temario", nombre_corto="ST")
        asignacion = MateriaCurso.objects.create(grupo=self.curso, materia=materia)
        ProfesorMateriaCurso.objects.create(partner=self.docente, materia_curso=asignacion)
        self.client.force_login(self.user)
        url = reverse("academico:docente_horarios")
        response = self.client.get(url, HTTP_HOST="localhost")
        self.assertNotContains(response, "Editar temario")
        self.assertContains(response, "Solicita a coordinación")
        self.grant_assigned_topic_permissions()
        response = self.client.get(url, HTTP_HOST="localhost")
        edit_url = reverse("academico:coordinacion_planificacion_materia_editar", args=[materia.pk])
        self.assertContains(response, f'href="{edit_url}"')
        self.assertContains(response, "Editar temario")
        self.assertEqual(self.client.get(edit_url, HTTP_HOST="localhost").status_code, 200)

    def test_docente_calendar_view_renders_week_calendar_and_export_link(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_calendario"),
            {"fecha": self.revision.fecha.isoformat()},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mi calendario")
        self.assertContains(response, "docente-calendar-full-panel")
        self.assertContains(response, "Descargar Excel")
        self.assertContains(response, "agendaWeek")
        self.assertTrue(response.context["has_events"])
        self.assertGreaterEqual(response.context["week_count"], 1)

    def test_docente_calendar_export_returns_weekly_excel(self):
        self.revision.tema = self.tema
        self.revision.subtema = self.subtema
        self.revision.save(update_fields=["tema", "subtema"])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_calendario_exportar"),
            {"fecha": self.revision.fecha.isoformat()},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        workbook = load_workbook(BytesIO(response.content))
        sheet = workbook.active
        values = [cell.value for row in sheet.iter_rows() for cell in row if cell.value]
        schedule_cell = self.find_cell_containing(sheet, "Matematicas")

        self.assertTrue(any("Matematicas" in str(value) for value in values))
        self.assertTrue(any("Grupo A" in str(value) for value in values))
        self.assertIn("Numeros", schedule_cell.value)
        self.assertIn("Suma", schedule_cell.value)
        self.assertTrue(schedule_cell.alignment.wrap_text)
        self.assertEqual(schedule_cell.alignment.vertical, "top")
        self.assertEqual(sheet.column_dimensions["B"].width, 30)
        self.assertGreaterEqual(sheet.row_dimensions[schedule_cell.row].height, 78)

    def test_academic_planning_export_fits_and_combines_overlapping_slots(self):
        self.make_superuser()
        another_course = Curso.objects.create(nombre="Grupo B", activo=True)
        another_aula = Aula.objects.create(nombre="Aula 2")
        another_aula_curso = AulaCurso.objects.create(aula=another_aula, curso=another_course)
        another_horario_aula_curso = HorarioAulaCurso.objects.create(
            aula_curso=another_aula_curso,
            horario_dia=self.horario_aula_curso.horario_dia,
        )
        another_materia_curso = MateriaCurso.objects.create(materia=self.materia, grupo=another_course)
        ProfesorMateriaCurso.objects.create(partner=self.docente, materia_curso=another_materia_curso)
        Clase.objects.create(
            horario_aula_curso=another_horario_aula_curso,
            materia_curso=another_materia_curso,
            fecha=self.pendiente.fecha,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:planificacion_academica_exportar"),
            {"tipo": "general"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        workbook = load_workbook(BytesIO(response.content))
        sheet = workbook["General"]
        schedule_cell = self.find_cell_containing_all(sheet, "Grupo A", "Grupo B")

        self.assertIn("Grupo B", schedule_cell.value)
        self.assertIn("\n\n", schedule_cell.value)
        self.assertTrue(schedule_cell.alignment.wrap_text)
        self.assertEqual(schedule_cell.alignment.vertical, "top")
        self.assertEqual(sheet.column_dimensions["B"].width, 30)
        self.assertGreaterEqual(sheet.row_dimensions[schedule_cell.row].height, 130)

    def test_academic_planning_updates_future_class_without_delete_error(self):
        self.create_periodo_for_course()
        self.make_superuser()
        self.pendiente.tema = self.tema
        self.pendiente.subtema = self.subtema
        self.pendiente.descripcion = "Planificacion previa."
        self.pendiente.estado_planificacion = "rechazada"
        self.pendiente.save(update_fields=["tema", "subtema", "descripcion", "estado_planificacion"])
        self.pendiente.competencias.add(self.competencia)
        self.pendiente.estrategias.add(self.estrategia)
        self.pendiente.recursos.add(self.recurso)
        nueva_materia = Materia.objects.create(nombre="Lenguaje", nombre_corto="LEN", color="#2563eb")
        nueva_materia_curso = MateriaCurso.objects.create(materia=nueva_materia, grupo=self.curso)
        nueva_planificacion = PlanificacionDocente.objects.create(
            materia_curso=nueva_materia_curso,
            nombre="Plan lenguaje",
        )
        Tema.objects.create(planificacion=nueva_planificacion, nombre="Lectura", orden=1)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": self.pendiente.fecha.isoformat(),
                "materia": nueva_materia.pk,
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pendiente.materia_curso.materia, nueva_materia)
        self.assertEqual(self.pendiente.estado_planificacion, "pendiente")
        self.assertIsNone(self.pendiente.tema)
        self.assertFalse(self.pendiente.recursos.exists())

    def test_academic_planning_selector_lists_subjects_without_topics(self):
        self.create_periodo_for_course()
        self.make_superuser()
        nueva_materia = Materia.objects.create(nombre="Lenguaje", nombre_corto="LEN", color="#2563eb")
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:planificacion_academica"),
            {"curso": self.curso.pk},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'<option value="{self.materia.pk}">Matematicas</option>', html=True)
        self.assertContains(response, f'<option value="{nueva_materia.pk}">Lenguaje</option>', html=True)
        self.assertEqual(response.context["materias_asignables"], [nueva_materia, self.materia])

    def test_academic_planning_assigns_subject_without_topics(self):
        self.create_periodo_for_course()
        self.make_superuser()
        nueva_materia = Materia.objects.create(nombre="Lenguaje", nombre_corto="LEN", color="#2563eb")
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": self.pendiente.fecha.isoformat(),
                "materia": nueva_materia.pk,
            },
            follow=True,
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.pendiente.materia_curso.materia, nueva_materia)
        self.assertEqual(self.pendiente.materia_curso.grupo, self.curso)
        self.assertIsNone(self.pendiente.tema)

    def test_academic_planning_can_assign_subject_with_base_topics_to_group(self):
        self.create_periodo_for_course()
        self.make_superuser()
        nueva_materia = Materia.objects.create(nombre="Lenguaje", nombre_corto="LEN", color="#2563eb")
        materia_tema = MateriaTema.objects.create(materia=nueva_materia, nombre="Lectura", orden=1)
        MateriaSubtema.objects.create(tema=materia_tema, nombre="Comprension", orden=1)
        self.client.force_login(self.user)

        page_response = self.client.get(
            reverse("academico:planificacion_academica"),
            {"curso": self.curso.pk},
            HTTP_HOST="localhost",
        )
        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": self.pendiente.fecha.isoformat(),
                "materia": nueva_materia.pk,
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, f'<option value="{nueva_materia.pk}">Lenguaje</option>', html=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pendiente.materia_curso.materia, nueva_materia)
        generated_tema = self.pendiente.materia_curso.planificaciones.get().temas_planificacion.get(nombre="Lectura")
        self.assertEqual(generated_tema.materia_tema, materia_tema)
        self.assertTrue(generated_tema.subtemas_planificacion.filter(nombre="Comprension").exists())

    def test_academic_planning_calendar_opens_on_today_inside_period(self):
        today = timezone.localdate()
        periodo = Periodo.objects.create(
            nombre="Periodo vigente",
            fecha_inicio=today - timedelta(days=14),
            fecha_fin=today + timedelta(days=35),
        )
        CursoPeriodo.objects.create(curso=self.curso, periodo=periodo)
        self.make_superuser()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:planificacion_academica"),
            {"curso": self.curso.pk},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["calendar_default_date"], today.isoformat())

    def test_periodo_edit_loads_dates_with_modern_datepicker(self):
        self.make_superuser()
        today = timezone.localdate()
        periodo = Periodo.objects.create(
            nombre="Periodo editable",
            fecha_inicio=today,
            fecha_fin=today + timedelta(days=30),
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:periodo_editar", args=[periodo.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "flatpickr.min.css")
        self.assertContains(response, "InstitutoDatePicker.init")
        self.assertContains(response, "js-date-picker")
        self.assertContains(response, f'value="{today.isoformat()}"')
        self.assertContains(response, f'value="{(today + timedelta(days=30)).isoformat()}"')

    def test_materia_form_uses_custom_color_picker(self):
        self.make_superuser()
        self.client.force_login(self.user)

        response = self.client.get(reverse("academico:materia_nueva"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "subject-color-picker")
        self.assertContains(response, "data-color-trigger")
        self.assertContains(response, "data-color-popover")
        self.assertContains(response, "data-color-honeycomb")
        self.assertContains(response, "subject-color-row")
        self.assertContains(response, "dataset.colorTone")
        self.assertContains(response, "data-color-preview")
        self.assertContains(response, 'data-color-input=""')
        self.assertNotContains(response, 'type="color"')

    def test_materia_form_saves_hex_color(self):
        self.make_superuser()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:materia_nueva"),
            {
                "nombre": "Historia",
                "nombre_corto": "HIS",
                "color": "0F766E",
                "descripcion": "",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Materia.objects.get(nombre="Historia").color, "#0f766e")

    def grant_assigned_topic_permissions(self):
        group = Group.objects.create(name="Temas propios prueba")
        group.permissions.add(*Permission.objects.filter(
            content_type__app_label="academico",
            codename__in=["view_tema", "change_tema", "add_tema", "restrict_to_assigned_materiatema"],
        ))
        self.user.groups.add(group)
        self.client.force_login(self.user)

    def test_assigned_topics_scope_filters_list_selector_and_suggestions(self):
        other = Materia.objects.create(nombre="Materia ajena", nombre_corto="AJ")
        other_course = MateriaCurso.objects.create(materia=other, grupo=self.curso)
        MateriaTema.objects.create(materia=other, nombre="Tema privado")
        self.grant_assigned_topic_permissions()
        response = self.client.get(reverse("academico:coordinacion_planificacion_list"), HTTP_HOST="localhost")
        self.assertEqual(list(response.context["asignaciones"]), [self.materia_curso])
        response = self.client.get(reverse("academico:coordinacion_planificacion_nueva"), HTTP_HOST="localhost")
        self.assertEqual(list(response.context["form"].fields["materia"].queryset), [self.materia])
        self.assertNotIn("Tema privado", response.context["tema_suggestions"])
        other_plan = PlanificacionDocente.objects.create(materia_curso=other_course, nombre="Plan ajeno")
        other_topic = Tema.objects.create(planificacion=other_plan, nombre="Tema ajeno")
        response = self.client.get(reverse("academico:tema_list"), HTTP_HOST="localhost")
        self.assertNotContains(response, "Tema ajeno")
        url = reverse("academico:tema_editar", args=[other_topic.pk])
        self.assertEqual(self.client.get(url, HTTP_HOST="localhost").status_code, 404)
        response = self.client.post(reverse("academico:tema_nuevo"), {
            "planificacion": other_plan.pk, "nombre": "No autorizado", "orden": 1,
        }, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Tema.objects.filter(nombre="No autorizado").exists())
        for name, pk in [("coordinacion_planificacion_materia_editar", other.pk), ("coordinacion_planificacion_editar", other_course.pk)]:
            url = reverse("academico:" + name, args=[pk])
            self.assertEqual(self.client.get(url, HTTP_HOST="localhost").status_code, 404)
            self.assertEqual(self.client.post(url, {}, HTTP_HOST="localhost").status_code, 404)

    def test_assigned_topics_scope_validates_post_and_allows_own_topics(self):
        other = Materia.objects.create(nombre="Materia ajena", nombre_corto="AJ")
        self.grant_assigned_topic_permissions()
        payload = {
            "materia": other.pk, "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "0",
            "form-0-nombre": "Tema nuevo", "form-0-orden": "1",
            "form-0-subtemas-TOTAL_FORMS": "1", "form-0-subtemas-0-nombre": "Subtema nuevo",
        }
        url = reverse("academico:coordinacion_planificacion_nueva")
        response = self.client.post(url, payload, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertIn("materia", response.context["form"].errors)
        self.assertFalse(MateriaTema.objects.filter(materia=other).exists())
        payload["materia"] = self.materia.pk
        response = self.client.post(url, payload, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 302)
        tema = MateriaTema.objects.get(materia=self.materia, nombre="Tema nuevo")
        self.assertTrue(tema.subtemas_base.filter(nombre="Subtema nuevo").exists())

    def test_assigned_topics_scope_without_partner_is_empty(self):
        self.grant_assigned_topic_permissions()
        self.docente.usuario = None
        self.docente.save(update_fields=["usuario"])
        response = self.client.get(reverse("academico:coordinacion_planificacion_nueva"), HTTP_HOST="localhost")
        self.assertFalse(response.context["form"].fields["materia"].queryset.exists())

    def test_coordinator_sees_all_topic_assignments(self):
        other = Materia.objects.create(nombre="Materia ajena", nombre_corto="AJ")
        other_course = MateriaCurso.objects.create(materia=other, grupo=self.curso)
        self.client.force_login(self.create_coordinator())
        response = self.client.get(reverse("academico:coordinacion_planificacion_list"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertIn(other_course, response.context["asignaciones"])
        response = self.client.get(reverse("academico:coordinacion_planificacion_materia_editar", args=[other.pk]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)

    def test_coordinacion_topic_create_only_selects_subject(self):
        coordinator = self.create_coordinator()
        self.client.force_login(coordinator)

        response = self.client.get(
            reverse("academico:coordinacion_planificacion_nueva"),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Materia")
        self.assertContains(response, 'name="materia"')
        self.assertNotContains(response, "Materia / grupo")
        self.assertNotContains(response, 'name="materia_curso"')
        self.assertNotContains(response, "Docente asignado")

    def test_coordinacion_topic_create_applies_subject_topics_to_existing_groups(self):
        coordinator = self.create_coordinator()
        grupo_b = Curso.objects.create(nombre="Grupo B", activo=True)
        materia_curso_b = MateriaCurso.objects.create(materia=self.materia, grupo=grupo_b)
        self.client.force_login(coordinator)

        response = self.client.post(
            reverse("academico:coordinacion_planificacion_nueva"),
            {
                "materia": self.materia.pk,
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-tema_id": "",
                "form-0-nombre": "Algebra",
                "form-0-detalle": "",
                "form-0-orden": "1",
                "form-0-subtemas-TOTAL_FORMS": "1",
                "form-0-subtemas-0-id": "",
                "form-0-subtemas-0-nombre": "Polinomios",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("academico:coordinacion_planificacion_materia_editar", args=[self.materia.pk]),
        )
        materia_tema = MateriaTema.objects.get(materia=self.materia, nombre="Algebra")
        self.assertTrue(materia_tema.subtemas_base.filter(nombre="Polinomios").exists())
        for materia_curso in [self.materia_curso, materia_curso_b]:
            planificacion = PlanificacionDocente.objects.get(materia_curso=materia_curso)
            tema = planificacion.temas_planificacion.get(nombre="Algebra")
            self.assertEqual(tema.materia_tema, materia_tema)
            self.assertTrue(tema.subtemas_planificacion.filter(nombre="Polinomios").exists())

    def test_coordinacion_topic_editor_rejects_duplicate_topic_names_without_integrity_error(self):
        coordinator = self.create_coordinator()
        first_topic = MateriaTema.objects.create(
            materia=self.materia,
            nombre="Operaciones con naturales y decimales",
            orden=1,
        )
        second_topic = MateriaTema.objects.create(
            materia=self.materia,
            nombre="Operaciones con fracciones y decimales",
            orden=2,
        )
        self.client.force_login(coordinator)

        response = self.client.post(
            reverse("academico:coordinacion_planificacion_editar", args=[self.materia_curso.pk]),
            {
                "materia": self.materia.pk,
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "2",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-tema_id": first_topic.pk,
                "form-0-nombre": "  operaciones CON fracciones y decimales  ",
                "form-0-detalle": "",
                "form-0-orden": "1",
                "form-0-subtemas-TOTAL_FORMS": "0",
                "form-1-tema_id": second_topic.pk,
                "form-1-nombre": "Operaciones con fracciones y decimales",
                "form-1-detalle": "",
                "form-1-orden": "2",
                "form-1-subtemas-TOTAL_FORMS": "0",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        expected_error = (
            'El tema "operaciones CON fracciones y decimales" está repetido en las posiciones 1 y 2. '
            "Cada tema de la materia debe tener un nombre diferente."
        )
        self.assertEqual(response.context["formset"].forms[0].errors["nombre"], [expected_error])
        self.assertEqual(response.context["formset"].forms[1].errors["nombre"], [expected_error])
        self.assertEqual(response.context["formset"].error_summary, [expected_error])
        self.assertContains(response, "Revisa estos nombres repetidos")
        first_topic.refresh_from_db()
        second_topic.refresh_from_db()
        self.assertEqual(first_topic.nombre, "Operaciones con naturales y decimales")
        self.assertEqual(second_topic.nombre, "Operaciones con fracciones y decimales")

    def test_coordinacion_topic_editor_identifies_duplicate_subtopics_and_preserves_all_rows(self):
        coordinator = self.create_coordinator()
        materia_tema = MateriaTema.objects.create(
            materia=self.materia,
            nombre="Álgebra",
            orden=1,
        )
        first_subtopic = MateriaSubtema.objects.create(
            tema=materia_tema,
            nombre="Productos notables",
            orden=1,
        )
        second_subtopic = MateriaSubtema.objects.create(
            tema=materia_tema,
            nombre="Factorización",
            orden=2,
        )
        self.client.force_login(coordinator)

        response = self.client.post(
            reverse("academico:coordinacion_planificacion_materia_editar", args=[self.materia.pk]),
            {
                "materia": self.materia.pk,
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-tema_id": materia_tema.pk,
                "form-0-nombre": "Álgebra",
                "form-0-detalle": "",
                "form-0-orden": "1",
                "form-0-subtemas-TOTAL_FORMS": "3",
                "form-0-subtemas-0-id": first_subtopic.pk,
                "form-0-subtemas-0-nombre": " Productos notables ",
                "form-0-subtemas-1-id": second_subtopic.pk,
                "form-0-subtemas-1-nombre": "productos NOTABLES",
                "form-0-subtemas-2-id": "",
                "form-0-subtemas-2-nombre": "Trinomios",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        displayed_subtopics = response.context["formset"].forms[0].initial["subtemas"]
        self.assertEqual(
            [item["nombre"] for item in displayed_subtopics],
            ["Productos notables", "productos NOTABLES", "Trinomios"],
        )
        expected_error = 'El subtema "Productos notables" está repetido en las posiciones 1 y 2 del tema "Álgebra".'
        self.assertEqual(displayed_subtopics[0]["errors"], [expected_error])
        self.assertEqual(displayed_subtopics[1]["errors"], [expected_error])
        self.assertEqual(displayed_subtopics[2]["errors"], [])
        self.assertEqual(response.context["formset"].error_summary, [expected_error])
        self.assertContains(response, "Revisa estos nombres repetidos")
        self.assertContains(response, 'value="Trinomios"')
        materia_tema.refresh_from_db()
        self.assertEqual(
            list(materia_tema.subtemas_base.order_by("orden").values_list("nombre", flat=True)),
            ["Productos notables", "Factorización"],
        )

    def test_coordinacion_topic_create_allows_subject_without_existing_group_link(self):
        coordinator = self.create_coordinator()
        nueva_materia = Materia.objects.create(nombre="Fisica", nombre_corto="FIS", color="#0891b2")
        self.client.force_login(coordinator)

        response = self.client.post(
            reverse("academico:coordinacion_planificacion_nueva"),
            {
                "materia": nueva_materia.pk,
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-tema_id": "",
                "form-0-nombre": "Movimiento",
                "form-0-detalle": "",
                "form-0-orden": "1",
                "form-0-subtemas-TOTAL_FORMS": "1",
                "form-0-subtemas-0-id": "",
                "form-0-subtemas-0-nombre": "Velocidad",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("academico:coordinacion_planificacion_materia_editar", args=[nueva_materia.pk]),
        )
        materia_tema = MateriaTema.objects.get(materia=nueva_materia, nombre="Movimiento")
        self.assertTrue(materia_tema.subtemas_base.filter(nombre="Velocidad").exists())
        self.assertFalse(MateriaCurso.objects.filter(materia=nueva_materia).exists())

    def test_academic_planning_can_remove_subject_assignment_with_cleared_selector(self):
        self.create_periodo_for_course()
        self.make_superuser()
        self.pendiente.tema = self.tema
        self.pendiente.save(update_fields=["tema"])
        self.pendiente.sync_subtemas_planificados([self.subtema])
        self.client.force_login(self.user)

        page_response = self.client.get(
            reverse("academico:planificacion_academica"),
            {"curso": self.curso.pk},
            HTTP_HOST="localhost",
        )

        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, "allowClear: true")
        self.assertContains(page_response, "select2:clearing")
        self.assertContains(page_response, "select2:opening")
        self.assertNotContains(page_response, "Quitar materia de esta clase")

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": self.pendiente.fecha.isoformat(),
                "materia": "",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Clase.objects.filter(pk=self.pendiente.pk).exists())

    def test_academic_planning_does_not_update_approved_class(self):
        self.create_periodo_for_course()
        self.make_superuser()
        nueva_materia = Materia.objects.create(nombre="Lenguaje", nombre_corto="LEN", color="#2563eb")
        self.revision.estado_planificacion = "aprobada"
        self.revision.save(update_fields=["estado_planificacion"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": self.revision.fecha.isoformat(),
                "materia": nueva_materia.pk,
            },
            follow=True,
            HTTP_HOST="localhost",
        )
        self.revision.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.revision.materia_curso, self.materia_curso)
        self.assertFalse(MateriaCurso.objects.filter(materia=nueva_materia, grupo=self.curso).exists())
        self.assertContains(response, "La clase no se puede modificar porque tiene una planificacion enviada o aprobada.")
        self.assertContains(response, "approved-locked-event")

    def test_academic_planning_assigns_single_day_docente_override(self):
        self.create_periodo_for_course()
        self.make_superuser()
        reemplazo, reemplazo_user = self.create_docente()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": self.pendiente.fecha.isoformat(),
                "materia": self.materia.pk,
                "docente": reemplazo.pk,
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()
        self.revision.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pendiente.docente, reemplazo)
        self.assertTrue(self.pendiente.docente_override)
        self.assertIsNone(self.revision.docente)
        profesor_materia_curso = ProfesorMateriaCurso.objects.get(partner=reemplazo, materia_curso=self.materia_curso)
        self.assertTrue(profesor_materia_curso.auto_generada_por_clases)
        self.assertTrue(PlanificacionTema.objects.filter(profesor_materia_curso=profesor_materia_curso, tema=self.tema).exists())

        self.client.force_login(reemplazo_user)
        docente_response = self.client.get(reverse("academico:docente_horarios"), HTTP_HOST="localhost")

        self.assertEqual(docente_response.status_code, 200)
        self.assertEqual(docente_response.context["planificacion_stats"]["total"], 1)
        self.assertEqual(len(docente_response.context["tema_cards"]), 1)

    def test_academic_planning_removing_class_cleans_auto_docente_topic_plans(self):
        self.create_periodo_for_course()
        self.make_superuser()
        reemplazo, _ = self.create_docente()
        self.client.force_login(self.user)

        assign_response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": self.pendiente.fecha.isoformat(),
                "materia": self.materia.pk,
                "docente": reemplazo.pk,
            },
            HTTP_HOST="localhost",
        )
        profesor_materia_curso = ProfesorMateriaCurso.objects.get(partner=reemplazo, materia_curso=self.materia_curso)

        remove_response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": self.pendiente.fecha.isoformat(),
                "materia": "",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(assign_response.status_code, 302)
        self.assertEqual(remove_response.status_code, 302)
        self.assertFalse(Clase.objects.filter(pk=self.pendiente.pk).exists())
        self.assertFalse(ProfesorMateriaCurso.objects.filter(pk=profesor_materia_curso.pk).exists())
        self.assertFalse(PlanificacionTema.objects.filter(profesor_materia_curso_id=profesor_materia_curso.pk).exists())

    def test_docente_subject_assignment_removal_blocks_locked_class_planifications(self):
        self.make_superuser()
        self.revision.estado_planificacion = "aprobada"
        self.revision.save(update_fields=["estado_planificacion"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_docente"),
            {
                "materia_curso": self.materia_curso.pk,
                "docente": "",
                "grupo": self.curso.pk,
            },
            follow=True,
            HTTP_HOST="localhost",
        )
        self.revision.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ProfesorMateriaCurso.objects.filter(
                pk=self.profesor_materia_curso.pk,
                auto_generada_por_clases=False,
            ).exists()
        )
        self.assertFalse(self.revision.docente_override)
        self.assertContains(response, "No se puede quitar el docente porque hay clases con planificacion enviada o aprobada.")

    def test_docente_subject_assignment_replacement_preserves_locked_classes_for_previous_teacher(self):
        self.make_superuser()
        reemplazo, reemplazo_user = self.create_docente()
        self.revision.estado_planificacion = "aprobada"
        self.revision.save(update_fields=["estado_planificacion"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_docente"),
            {
                "materia_curso": self.materia_curso.pk,
                "docente": reemplazo.pk,
                "grupo": self.curso.pk,
            },
            follow=True,
            HTTP_HOST="localhost",
        )
        self.revision.refresh_from_db()
        self.pendiente.refresh_from_db()
        previous_assignment = ProfesorMateriaCurso.objects.get(partner=self.docente, materia_curso=self.materia_curso)
        new_assignment = ProfesorMateriaCurso.objects.get(partner=reemplazo, materia_curso=self.materia_curso)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(previous_assignment.auto_generada_por_clases)
        self.assertFalse(new_assignment.auto_generada_por_clases)
        self.assertEqual(self.revision.docente, self.docente)
        self.assertTrue(self.revision.docente_override)
        self.assertIsNone(self.pendiente.docente)
        self.assertFalse(self.pendiente.docente_override)
        self.assertTrue(
            PlanificacionTema.objects.filter(profesor_materia_curso=previous_assignment, tema=self.tema).exists()
        )
        self.assertTrue(
            PlanificacionTema.objects.filter(profesor_materia_curso=new_assignment, tema=self.tema).exists()
        )

        self.client.force_login(reemplazo_user)
        docente_response = self.client.get(reverse("academico:docente_horarios"), HTTP_HOST="localhost")

        self.assertEqual(docente_response.status_code, 200)
        self.assertEqual(docente_response.context["planificacion_stats"]["total"], 3)
        self.assertNotIn(self.revision, [card["clase"] for card in docente_response.context["planificacion_cards"]])

        self.client.force_login(self.user)
        previous_docente_response = self.client.get(reverse("academico:docente_horarios"), HTTP_HOST="localhost")

        self.assertEqual(previous_docente_response.status_code, 200)
        self.assertEqual(previous_docente_response.context["planificacion_stats"]["total"], 1)

    def test_docente_bulk_assignment_removal_blocks_locked_class_planifications(self):
        self.make_superuser()
        self.revision.estado_planificacion = "aprobada"
        self.revision.save(update_fields=["estado_planificacion"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_docente_editar", args=[self.docente.pk]),
            {
                "docente": self.docente.pk,
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-grupo": self.curso.pk,
                "form-0-materia_curso": self.materia_curso.pk,
                "form-0-DELETE": "on",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ProfesorMateriaCurso.objects.filter(
                pk=self.profesor_materia_curso.pk,
                auto_generada_por_clases=False,
            ).exists()
        )
        self.assertContains(response, "No se puede quitar el docente porque hay clases con planificacion enviada o aprobada")

    def test_academic_planning_assigns_docente_from_selected_date_forward(self):
        self.create_periodo_for_course()
        self.make_superuser()
        reemplazo, reemplazo_user = self.create_docente()
        selected_date = self.rechazada.fecha
        future_date = selected_date + timedelta(days=7)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": selected_date.isoformat(),
                "materia": self.materia.pk,
                "docente": reemplazo.pk,
                "asignar_periodo": "on",
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()
        self.revision.refresh_from_db()
        self.rechazada.refresh_from_db()
        future_class = Clase.objects.get(horario_aula_curso=self.horario_aula_curso, fecha=future_date)
        previous_assignment = ProfesorMateriaCurso.objects.get(partner=self.docente, materia_curso=self.materia_curso)
        new_assignment = ProfesorMateriaCurso.objects.get(partner=reemplazo, materia_curso=self.materia_curso)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pendiente.docente, self.docente)
        self.assertTrue(self.pendiente.docente_override)
        self.assertEqual(self.revision.docente, self.docente)
        self.assertTrue(self.revision.docente_override)
        self.assertIsNone(self.rechazada.docente)
        self.assertFalse(self.rechazada.docente_override)
        self.assertIsNone(future_class.docente)
        self.assertFalse(future_class.docente_override)
        self.assertTrue(previous_assignment.auto_generada_por_clases)
        self.assertFalse(new_assignment.auto_generada_por_clases)

        self.client.force_login(reemplazo_user)
        replacement_response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.rechazada.pk]),
            HTTP_HOST="localhost",
        )
        locked_response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.revision.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(replacement_response.status_code, 200)
        self.assertEqual(locked_response.status_code, 404)

        self.client.force_login(self.user)
        assignment_response = self.client.get(
            reverse("academico:planificacion_docente"),
            {"grupo": self.curso.pk},
            HTTP_HOST="localhost",
        )

        self.assertEqual(assignment_response.status_code, 200)
        self.assertEqual(assignment_response.context["stats"]["asignadas"], 1)
        self.assertEqual(assignment_response.context["stats"]["pendientes"], 0)
        self.assertContains(assignment_response, "Docente Reemplazo")

    def test_academic_planning_can_leave_single_class_without_docente(self):
        self.create_periodo_for_course()
        self.make_superuser()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": self.pendiente.fecha.isoformat(),
                "materia": self.materia.pk,
                "docente": "__none__",
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.pendiente.docente)
        self.assertTrue(self.pendiente.docente_override)

        old_docente_response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(old_docente_response.status_code, 404)

    def test_academic_planning_can_restore_materia_docente_assignment(self):
        self.create_periodo_for_course()
        self.make_superuser()
        self.pendiente.docente = None
        self.pendiente.docente_override = True
        self.pendiente.save(update_fields=["docente", "docente_override"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": self.pendiente.fecha.isoformat(),
                "materia": self.materia.pk,
                "docente": "",
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.pendiente.docente)
        self.assertFalse(self.pendiente.docente_override)

        docente_response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(docente_response.status_code, 200)

    def test_academic_planning_does_not_change_submitted_class_docente(self):
        self.create_periodo_for_course()
        self.make_superuser()
        reemplazo, _ = self.create_docente()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "curso": self.curso.pk,
                "horario_aula_curso": self.horario_aula_curso.pk,
                "fecha": self.revision.fecha.isoformat(),
                "materia": self.materia.pk,
                "docente": reemplazo.pk,
            },
            follow=True,
            HTTP_HOST="localhost",
        )
        self.revision.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.revision.docente)
        self.assertFalse(self.revision.docente_override)
        self.assertContains(response, "La clase no se puede modificar porque tiene una planificacion enviada o aprobada.")

    def test_academic_planning_deletes_empty_schedule(self):
        self.create_periodo_for_course()
        self.make_superuser()
        self.client.force_login(self.user)
        url = reverse("academico:planificacion_academica")
        for fecha in [None, self.pendiente.fecha]:
            horario, _ = Horario.objects.get_or_create(hora_inicio=time(20, 0), hora_fin=time(21, 0))
            dia, _ = HorarioDia.objects.get_or_create(horario=horario, dia=self.horario_aula_curso.horario_dia.dia)
            bloque = HorarioAulaCurso.objects.create(
                aula_curso=self.horario_aula_curso.aula_curso, horario_dia=dia, fecha=fecha,
            )
            response = self.client.get(url, {"curso": self.curso.pk}, HTTP_HOST="localhost")
            events = json.loads(response.context["calendar_events_json"])
            self.assertTrue(any(event["horarioId"] == bloque.pk and event["canDeleteSchedule"] for event in events))
            response = self.client.post(url, {
                "planning_action": "delete_schedule", "curso": self.curso.pk,
                "schedule_horario_aula_curso": bloque.pk,
            }, HTTP_HOST="localhost")
            self.assertEqual(response.status_code, 302)
            self.assertFalse(HorarioAulaCurso.objects.filter(pk=bloque.pk).exists())
            self.assertTrue(HorarioDia.objects.filter(pk=dia.pk).exists())

    def test_superuser_resets_planning_and_preserves_teacher_assignment(self):
        self.create_periodo_for_course()
        self.make_superuser()
        self.client.force_login(self.user)
        clase = self.revision
        clase.estado_planificacion = "aprobada"
        clase.tema = self.tema
        clase.subtema = self.subtema
        clase.docente = self.docente
        clase.docente_override = True
        clase.revisado_por = self.docente
        clase.fecha_revision = timezone.now()
        clase.asistencia_cerrada = True
        clase.revision_tema_ok = True
        clase.save()
        clase.sync_subtemas_planificados([self.subtema])
        clase.competencias.add(self.competencia)
        clase.estrategias.add(self.estrategia)
        clase.recursos.add(self.recurso)
        ClaseAsistencia.objects.create(clase=clase, estudiante=self.docente)
        ClaseHoraDocente.objects.create(clase=clase, docente=self.docente, horas=1)
        page = self.client.get(reverse("academico:planificacion_academica"), {"curso": self.curso.pk}, HTTP_HOST="localhost")
        self.assertContains(page, "Borrar planificación definitivamente")
        event = next(item for item in json.loads(page.context["calendar_events_json"]) if item["claseId"] == clase.pk)
        self.assertTrue(event["canResetPlanning"])
        response = self.client.post(reverse("academico:planificacion_academica"), {
            "planning_action": "reset_planning", "curso": self.curso.pk,
            "clase": clase.pk, "confirm_reset": "1",
        }, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 302)
        clase.refresh_from_db()
        self.assertEqual(clase.estado_planificacion, "pendiente")
        self.assertEqual(clase.descripcion, "")
        self.assertIsNone(clase.tema)
        self.assertIsNone(clase.subtema)
        self.assertIsNone(clase.revisado_por)
        self.assertIsNone(clase.fecha_revision)
        self.assertFalse(clase.asistencia_cerrada)
        self.assertFalse(clase.revision_tema_ok)
        self.assertEqual(clase.docente, self.docente)
        self.assertTrue(clase.docente_override)
        self.assertEqual(clase.materia_curso, self.materia_curso)
        for related in [clase.clase_subtemas, clase.competencias, clase.estrategias, clase.clase_recursos, clase.asistencias_clase]:
            self.assertFalse(related.exists())
        self.assertFalse(ClaseHoraDocente.objects.filter(clase=clase).exists())
        self.assertTrue(Recurso.objects.filter(pk=self.recurso.pk).exists())
        self.rechazada.refresh_from_db()
        self.assertEqual(self.rechazada.estado_planificacion, "rechazada")
        self.user.is_superuser = False
        self.user.save(update_fields=["is_superuser"])
        self.user.user_permissions.add(Permission.objects.get(codename="change_clase", content_type__app_label="academico"))
        response = self.client.get(reverse("academico:docente_clase_planificar", args=[clase.pk]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)

    def test_planning_reset_denies_staff_even_with_all_academic_permissions(self):
        self.create_periodo_for_course()
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label="academico"))
        self.client.force_login(self.user)
        page = self.client.get(reverse("academico:planificacion_academica"), {"curso": self.curso.pk}, HTTP_HOST="localhost")
        self.assertNotContains(page, "Borrar planificación definitivamente")
        self.assertTrue(all(not item["canResetPlanning"] for item in json.loads(page.context["calendar_events_json"])))
        response = self.client.post(reverse("academico:planificacion_academica"), {
            "planning_action": "reset_planning", "curso": self.curso.pk,
            "clase": self.revision.pk, "confirm_reset": "1",
        }, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 403)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.estado_planificacion, "revision")

    def test_planning_reset_requires_confirmation_and_matching_group(self):
        self.make_superuser()
        self.client.force_login(self.user)
        url = reverse("academico:planificacion_academica")
        payload = {"planning_action": "reset_planning", "curso": self.curso.pk, "clase": self.revision.pk}
        self.assertEqual(self.client.post(url, payload, HTTP_HOST="localhost").status_code, 302)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.estado_planificacion, "revision")
        otro = Curso.objects.create(nombre="Otro grupo", activo=True)
        payload.update(curso=otro.pk, confirm_reset="1")
        self.assertEqual(self.client.post(url, payload, HTTP_HOST="localhost").status_code, 404)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.estado_planificacion, "revision")

    def test_academic_planning_does_not_delete_schedule_with_classes(self):
        self.make_superuser()
        self.client.force_login(self.user)
        response = self.client.post(reverse("academico:planificacion_academica"), {
            "planning_action": "delete_schedule", "curso": self.curso.pk,
            "schedule_horario_aula_curso": self.horario_aula_curso.pk,
        }, follow=True, HTTP_HOST="localhost")
        self.assertContains(response, "ya tiene clases asignadas o planificadas")
        self.assertTrue(HorarioAulaCurso.objects.filter(pk=self.horario_aula_curso.pk).exists())
        self.assertEqual(Clase.objects.filter(horario_aula_curso=self.horario_aula_curso).count(), 4)

    def test_superuser_deletes_schedule_with_classes_after_confirmation(self):
        self.create_periodo_for_course()
        self.make_superuser()
        self.client.force_login(self.user)
        self.revision.estado_planificacion = "aprobada"
        self.revision.save(update_fields=["estado_planificacion"])
        self.revision.competencias.add(self.competencia)
        self.revision.recursos.add(self.recurso)
        ClaseAsistencia.objects.create(clase=self.revision, estudiante=self.docente)
        ClaseHoraDocente.objects.create(clase=self.revision, docente=self.docente, horas=1)
        url = reverse("academico:planificacion_academica")
        page = self.client.get(url, {"curso": self.curso.pk}, HTTP_HOST="localhost")
        event = next(item for item in json.loads(page.context["calendar_events_json"]) if item["horarioId"] == self.horario_aula_curso.pk)
        self.assertTrue(event["canDeleteSchedule"])
        self.assertEqual(event["scheduleClassCount"], 4)
        payload = {
            "planning_action": "delete_schedule", "curso": self.curso.pk,
            "schedule_horario_aula_curso": self.horario_aula_curso.pk,
            "confirm_delete_classes": "3",
        }
        self.client.post(url, payload, HTTP_HOST="localhost")
        self.assertTrue(Clase.objects.filter(pk=self.revision.pk).exists())
        payload["confirm_delete_classes"] = "4"
        response = self.client.post(url, payload, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(HorarioAulaCurso.objects.filter(pk=self.horario_aula_curso.pk).exists())
        self.assertFalse(Clase.objects.filter(horario_aula_curso_id=self.horario_aula_curso.pk).exists())
        self.assertFalse(ClaseAsistencia.objects.filter(clase_id=self.revision.pk).exists())
        self.assertFalse(ClaseHoraDocente.objects.filter(clase_id=self.revision.pk).exists())
        self.assertTrue(Recurso.objects.filter(pk=self.recurso.pk).exists())
        self.assertTrue(Horario.objects.filter(pk=self.horario.pk).exists())

    def test_staff_with_all_permissions_cannot_delete_occupied_schedule(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label="academico"))
        self.client.force_login(self.user)
        response = self.client.post(reverse("academico:planificacion_academica"), {
            "planning_action": "delete_schedule", "curso": self.curso.pk,
            "schedule_horario_aula_curso": self.horario_aula_curso.pk,
            "confirm_delete_classes": "4",
        }, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Clase.objects.filter(horario_aula_curso=self.horario_aula_curso).count(), 4)

    def test_academic_planning_delete_schedule_checks_permission_and_group(self):
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label="academico", codename="view_clase"))
        self.client.force_login(self.user)
        payload = {"planning_action": "delete_schedule", "curso": self.curso.pk,
                   "schedule_horario_aula_curso": self.horario_aula_curso.pk}
        url = reverse("academico:planificacion_academica")
        self.assertEqual(self.client.post(url, payload, HTTP_HOST="localhost").status_code, 403)
        self.make_superuser()
        otro = Curso.objects.create(nombre="Otro grupo", activo=True)
        payload["curso"] = otro.pk
        response = self.client.post(url, payload, follow=True, HTTP_HOST="localhost")
        self.assertContains(response, "Selecciona un horario valido para eliminar.")
        self.assertTrue(HorarioAulaCurso.objects.filter(pk=self.horario_aula_curso.pk).exists())

    def test_academic_planning_adds_schedule_block(self):
        periodo = self.create_periodo_for_course()
        self.make_superuser()
        aula = Aula.objects.create(nombre="Aula 2")
        dia, _ = Dia.objects.get_or_create(dia="Martes")
        selected_date = self.date_for_weekday(periodo, 1)
        self.client.force_login(self.user)

        page_response = self.client.get(
            reverse("academico:planificacion_academica"),
            {"curso": self.curso.pk},
            HTTP_HOST="localhost",
        )

        self.assertContains(page_response, "planificacionHorarioOffcanvas")
        self.assertContains(page_response, "selectable: canAddSchedule")
        self.assertContains(page_response, "Generar en todo el periodo preseleccionado")
        self.assertContains(page_response, "data-schedule-periodo-switch")
        self.assertNotContains(page_response, "Agregar bloque al calendario")

        response = self.client.post(
            f"{reverse('academico:planificacion_academica')}?curso={self.curso.pk}",
            {
                "planning_action": "add_schedule",
                "generar_periodo": "on",
                "schedule_fecha": selected_date.isoformat(),
                "schedule-aula": aula.pk,
                "schedule-dia": dia.pk,
                "schedule-hora_inicio": "10:00",
                "schedule-hora_fin": "11:00",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            HorarioAulaCurso.objects.filter(
                aula_curso__curso=self.curso,
                aula_curso__aula=aula,
                fecha__isnull=True,
                horario_dia__dia=dia,
                horario_dia__horario__hora_inicio=time(10, 0),
                horario_dia__horario__hora_fin=time(11, 0),
            ).exists()
        )

    def test_academic_planning_rejects_schedule_aula_overlap(self):
        periodo = self.create_periodo_for_course()
        self.make_superuser()
        dia = self.horario_aula_curso.horario_dia.dia
        selected_date = self.date_for_weekday(periodo, 0)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "planning_action": "add_schedule",
                "curso": self.curso.pk,
                "generar_periodo": "on",
                "schedule_fecha": selected_date.isoformat(),
                "schedule-aula": self.aula.pk,
                "schedule-dia": dia.pk,
                "schedule-hora_inicio": "08:30",
                "schedule-hora_fin": "09:30",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El aula Aula 1 ya esta asignada")
        self.assertFalse(
            HorarioAulaCurso.objects.filter(
                aula_curso__curso=self.curso,
                aula_curso__aula=self.aula,
                horario_dia__dia=dia,
                horario_dia__horario__hora_inicio=time(8, 30),
                horario_dia__horario__hora_fin=time(9, 30),
            ).exists()
        )

    def test_academic_planning_adds_single_date_schedule_when_period_switch_off(self):
        periodo = self.create_periodo_for_course()
        self.make_superuser()
        aula = Aula.objects.create(nombre="Aula 3")
        dia, _ = Dia.objects.get_or_create(dia="Jueves")
        selected_date = self.date_for_weekday(periodo, 3)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "planning_action": "add_schedule",
                "curso": self.curso.pk,
                "generar_periodo": "off",
                "schedule_fecha": selected_date.isoformat(),
                "schedule-aula": aula.pk,
                "schedule-dia": dia.pk,
                "schedule-hora_inicio": "12:00",
                "schedule-hora_fin": "13:00",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        horario_aula_curso = HorarioAulaCurso.objects.get(
            aula_curso__curso=self.curso,
            aula_curso__aula=aula,
            fecha=selected_date,
            horario_dia__dia=dia,
            horario_dia__horario__hora_inicio=time(12, 0),
            horario_dia__horario__hora_fin=time(13, 0),
        )
        page_response = self.client.get(
            reverse("academico:planificacion_academica"),
            {"curso": self.curso.pk},
            HTTP_HOST="localhost",
        )
        events = [
            event
            for event in json.loads(page_response.context["calendar_events_json"])
            if event["horarioId"] == horario_aula_curso.pk
        ]

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["fecha"], selected_date.isoformat())
        self.assertTrue(events[0]["singleDate"])

    def test_academic_planning_updates_schedule_block(self):
        periodo = self.create_periodo_for_course()
        self.make_superuser()
        aula_origen = Aula.objects.create(nombre="Aula 4")
        aula_destino = Aula.objects.create(nombre="Aula 5")
        dia, _ = Dia.objects.get_or_create(dia="Martes")
        horario = Horario.objects.create(hora_inicio=time(10, 0), hora_fin=time(11, 0))
        horario_dia = HorarioDia.objects.create(dia=dia, horario=horario)
        aula_curso = AulaCurso.objects.create(aula=aula_origen, curso=self.curso)
        horario_aula_curso = HorarioAulaCurso.objects.create(aula_curso=aula_curso, horario_dia=horario_dia)
        selected_date = self.date_for_weekday(periodo, 1)
        self.client.force_login(self.user)

        page_response = self.client.get(
            reverse("academico:planificacion_academica"),
            {"curso": self.curso.pk},
            HTTP_HOST="localhost",
        )

        self.assertContains(page_response, "data-edit-schedule-button")
        self.assertContains(page_response, "aulaId")
        self.assertContains(page_response, "horaInicio")

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "planning_action": "update_schedule",
                "curso": self.curso.pk,
                "schedule_horario_aula_curso": horario_aula_curso.pk,
                "generar_periodo": "on",
                "schedule_fecha": selected_date.isoformat(),
                "schedule-aula": aula_destino.pk,
                "schedule-dia": dia.pk,
                "schedule-hora_inicio": "10:30",
                "schedule-hora_fin": "11:30",
            },
            HTTP_HOST="localhost",
        )
        horario_aula_curso.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(horario_aula_curso.aula_curso.aula, aula_destino)
        self.assertIsNone(horario_aula_curso.fecha)
        self.assertEqual(horario_aula_curso.horario_dia.horario.hora_inicio, time(10, 30))
        self.assertEqual(horario_aula_curso.horario_dia.horario.hora_fin, time(11, 30))

    def test_academic_planning_updates_schedule_block_to_single_date(self):
        periodo = self.create_periodo_for_course()
        self.make_superuser()
        aula = Aula.objects.create(nombre="Aula 6")
        dia, _ = Dia.objects.get_or_create(dia="Viernes")
        horario = Horario.objects.create(hora_inicio=time(14, 0), hora_fin=time(15, 0))
        horario_dia = HorarioDia.objects.create(dia=dia, horario=horario)
        aula_curso = AulaCurso.objects.create(aula=aula, curso=self.curso)
        horario_aula_curso = HorarioAulaCurso.objects.create(aula_curso=aula_curso, horario_dia=horario_dia)
        selected_date = self.date_for_weekday(periodo, 4)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "planning_action": "update_schedule",
                "curso": self.curso.pk,
                "schedule_horario_aula_curso": horario_aula_curso.pk,
                "generar_periodo": "off",
                "schedule_fecha": selected_date.isoformat(),
                "schedule-aula": aula.pk,
                "schedule-dia": dia.pk,
                "schedule-hora_inicio": "14:00",
                "schedule-hora_fin": "15:00",
            },
            HTTP_HOST="localhost",
        )
        horario_aula_curso.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(horario_aula_curso.fecha, selected_date)

    def test_academic_planning_does_not_update_schedule_with_approved_class(self):
        periodo = self.create_periodo_for_course()
        self.make_superuser()
        aula = Aula.objects.create(nombre="Aula 7")
        dia, _ = Dia.objects.get_or_create(dia="Martes")
        horario = Horario.objects.create(hora_inicio=time(15, 0), hora_fin=time(16, 0))
        horario_dia = HorarioDia.objects.create(dia=dia, horario=horario)
        aula_curso = AulaCurso.objects.create(aula=aula, curso=self.curso)
        horario_aula_curso = HorarioAulaCurso.objects.create(aula_curso=aula_curso, horario_dia=horario_dia)
        selected_date = self.date_for_weekday(periodo, 1)
        Clase.objects.create(
            horario_aula_curso=horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=selected_date,
            estado_planificacion="aprobada",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:planificacion_academica"),
            {
                "planning_action": "update_schedule",
                "curso": self.curso.pk,
                "schedule_horario_aula_curso": horario_aula_curso.pk,
                "generar_periodo": "on",
                "schedule_fecha": selected_date.isoformat(),
                "schedule-aula": aula.pk,
                "schedule-dia": dia.pk,
                "schedule-hora_inicio": "15:30",
                "schedule-hora_fin": "16:30",
            },
            HTTP_HOST="localhost",
        )
        horario_aula_curso.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No se puede modificar el horario porque tiene una planificacion enviada o aprobada.")
        self.assertEqual(horario_aula_curso.horario_dia.horario.hora_inicio, time(15, 0))
        self.assertEqual(horario_aula_curso.horario_dia.horario.hora_fin, time(16, 0))

    def test_docente_status_filter_limits_cards(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_horarios"),
            {"estado": "revision"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_filter"], "revision")
        self.assertEqual(len(response.context["planificacion_cards"]), 1)
        self.assertEqual(response.context["planificacion_cards"][0]["clase"], self.revision)

    def test_docente_observed_filter_limits_cards(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_horarios"),
            {"estado": "rechazada"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_filter"], "rechazada")
        self.assertEqual(len(response.context["planificacion_cards"]), 1)
        self.assertEqual(response.context["planificacion_cards"][0]["clase"], self.rechazada)

    def test_docente_class_planning_renders_workstation(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "teacher-plan-hero")
        self.assertContains(response, "teacher-submit-panel")
        self.assertContains(response, "Guardar borrador")
        self.assertContains(response, "teacher-chip-pool")
        self.assertContains(response, "data-available-chip")
        self.assertContains(response, "subtemas_nuevos")
        self.assertContains(response, "data-selected-list")
        self.assertNotContains(response, "Usar disponible")
        self.assertNotContains(response, "Crear nuevo")
        self.assertEqual(response.context["planning_total"], 4)

    def test_docente_class_planning_with_override_and_multiple_assignments(self):
        other_docente, _ = self.create_docente()
        ProfesorMateriaCurso.objects.create(
            partner=other_docente,
            materia_curso=self.materia_curso,
        )
        self.pendiente.docente = self.docente
        self.pendiente.docente_override = True
        self.pendiente.save(update_fields=["docente", "docente_override"])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["clase"], self.pendiente)

    def test_docente_topic_planning_assigns_available_class(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            {
                "tema_action": "assign",
                "clase_id": self.pendiente.pk,
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('academico:docente_tema_planificar', args=[self.planificacion_tema.pk])}#clase-{self.pendiente.pk}",
        )
        self.assertEqual(self.pendiente.tema, self.tema)
        self.assertIsNone(self.pendiente.subtema)
        self.assertEqual(self.pendiente.get_subtemas_planificados(), [])

    def test_docente_topic_planning_saves_multiple_subtopics_to_assigned_class(self):
        otro_subtema = Subtema.objects.create(tema=self.tema, nombre="Resta", orden=2)
        self.pendiente.tema = self.tema
        self.pendiente.save(update_fields=["tema"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            {
                "tema_action": "save_class",
                "clase_id": self.pendiente.pk,
                "subtema_ids": [self.subtema.pk, otro_subtema.pk],
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('academico:docente_tema_planificar', args=[self.planificacion_tema.pk])}#clase-{self.pendiente.pk}",
        )
        self.assertEqual(self.pendiente.tema, self.tema)
        self.assertEqual(self.pendiente.subtema, self.subtema)
        self.assertEqual(self.pendiente.get_subtemas_planificados(), [self.subtema, otro_subtema])

    def test_docente_topic_planning_renders_summary_cards_for_assigned_class(self):
        self.pendiente.tema = self.tema
        self.pendiente.save(update_fields=["tema"])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "topic-class-summary")
        self.assertContains(response, "topic-summary-block")
        self.assertContains(response, "Editar clase")
        self.assertContains(response, reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]))
        self.assertContains(response, "from_planificacion_tema")
        self.assertContains(response, "Agregar clase a la planificacion")
        self.assertNotContains(response, "data-topic-class-inline-form")
        self.assertNotContains(response, "data-open-class-picker")
        self.assertNotContains(response, "data-class-picker")
        self.assertNotContains(response, "Tomar clases para este tema")

    def test_docente_topic_planning_creates_new_subtema_from_inline_class(self):
        self.pendiente.tema = self.tema
        self.pendiente.save(update_fields=["tema"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            {
                "tema_action": "save_class",
                "clase_id": self.pendiente.pk,
                "subtemas_nuevos": "Multiplicacion de polinomios",
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()
        nuevo_subtema = Subtema.objects.get(tema=self.tema, nombre="Multiplicacion de polinomios")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(nuevo_subtema.orden, 2)
        self.assertEqual(self.pendiente.get_subtemas_planificados(), [nuevo_subtema])

    def test_docente_topic_planning_keeps_subtopics_used_by_another_class_available(self):
        self.pendiente.tema = self.tema
        self.pendiente.save(update_fields=["tema"])
        self.pendiente.sync_subtemas_planificados([self.subtema])
        otra_clase = self.create_class_for_date(
            self.pendiente.fecha + timedelta(days=21),
            time(10, 0),
            time(11, 0),
            aula_nombre="Aula subtema disponible",
        )
        otra_clase.tema = self.tema
        otra_clase.save(update_fields=["tema"])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            HTTP_HOST="localhost",
        )
        assigned_slots = response.context["assigned_classes"]
        otra_clase_slot = next(item for item in assigned_slots if item["clase"] == otra_clase)
        visible_subtemas = [item["subtema"] for item in otra_clase_slot["subtema_options"]]

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.subtema, visible_subtemas)

    def test_docente_topic_planning_keeps_classes_available_when_subtopics_are_done(self):
        self.pendiente.tema = self.tema
        self.pendiente.estado_planificacion = "revision"
        self.pendiente.save(update_fields=["tema", "estado_planificacion"])
        self.pendiente.sync_subtemas_planificados([self.subtema])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pending_subtema_count"], 0)
        self.assertTrue(response.context["available_classes"])
        self.assertContains(response, "Todos los subtemas del tema ya fueron planificados.")

    def test_docente_topic_planning_allows_next_class_before_current_is_sent(self):
        self.pendiente.tema = self.tema
        self.pendiente.save(update_fields=["tema"])
        otra_clase = self.create_class_for_date(
            self.pendiente.fecha + timedelta(days=21),
            time(10, 0),
            time(11, 0),
            aula_nombre="Aula clase bloqueada",
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["available_classes"])
        self.assertNotContains(response, "Envia a revision la clase agregada antes de tomar otra clase")

        response = self.client.post(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            {
                "tema_action": "assign",
                "clase_id": otra_clase.pk,
            },
            HTTP_HOST="localhost",
        )
        otra_clase.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(otra_clase.tema, self.tema)

    def test_docente_topic_planning_assigns_more_classes_when_subtopics_are_done(self):
        self.pendiente.tema = self.tema
        self.pendiente.save(update_fields=["tema"])
        self.pendiente.sync_subtemas_planificados([self.subtema])
        otra_clase = self.create_class_for_date(
            self.pendiente.fecha + timedelta(days=21),
            time(10, 0),
            time(11, 0),
            aula_nombre="Aula tema completo",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            {
                "tema_action": "assign",
                "clase_id": otra_clase.pk,
            },
            HTTP_HOST="localhost",
        )
        otra_clase.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(otra_clase.tema, self.tema)

    def test_docente_topic_planning_reuses_subtopic_in_another_class(self):
        self.pendiente.tema = self.tema
        self.pendiente.save(update_fields=["tema"])
        self.pendiente.sync_subtemas_planificados([self.subtema])
        otra_clase = self.create_class_for_date(
            self.pendiente.fecha + timedelta(days=21),
            time(10, 0),
            time(11, 0),
            aula_nombre="Aula subtema duplicado",
        )
        otra_clase.tema = self.tema
        otra_clase.save(update_fields=["tema"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            {
                "tema_action": "save_class",
                "clase_id": otra_clase.pk,
                "subtema_ids": [self.subtema.pk],
            },
            HTTP_HOST="localhost",
        )
        otra_clase.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(otra_clase.tema, self.tema)
        self.assertEqual(otra_clase.get_subtemas_planificados(), [self.subtema])

    def test_docente_topic_planning_sends_inline_class_to_review(self):
        self.pendiente.tema = self.tema
        self.pendiente.save(update_fields=["tema"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            {
                "tema_action": "send_class",
                "clase_id": self.pendiente.pk,
                "subtema_ids": [self.subtema.pk],
                "competencias_existentes": [self.competencia.pk],
                "estrategias_existentes": [self.estrategia.pk],
                "recursos_existentes": [self.recurso.pk],
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('academico:docente_tema_planificar', args=[self.planificacion_tema.pk])}#clase-{self.pendiente.pk}",
        )
        self.assertEqual(self.pendiente.estado_planificacion, "revision")
        self.assertEqual(self.pendiente.get_subtemas_planificados(), [self.subtema])
        self.assertIn(self.competencia, self.pendiente.competencias.all())
        self.assertIn(self.estrategia, self.pendiente.estrategias.all())
        self.assertIn(self.recurso, self.pendiente.recursos.all())

    def test_docente_class_planning_from_topic_opens_class_editor(self):
        self.pendiente.tema = self.tema
        self.pendiente.save(update_fields=["tema"])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            {"from_planificacion_tema": self.planificacion_tema.pk},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planificar clase")
        self.assertContains(response, self.tema.nombre)

    def test_docente_class_planning_only_shows_catalogs_for_its_subject(self):
        other_materia = Materia.objects.create(nombre="Anatomia", nombre_corto="ANA")
        other_competencia = Competencia.objects.create(nombre="Identifica estructuras anatomicas")
        other_estrategia = Estrategia.objects.create(nombre="Practica con modelos anatomicos")
        other_recurso = Recurso.objects.create(nombre="Modelo anatomico")
        other_competencia.materias.add(other_materia)
        other_estrategia.materias.add(other_materia)
        other_recurso.materias.add(other_materia)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            HTTP_HOST="localhost",
        )

        catalogs = {
            group["prefix"]: [item["obj"] for item in group["items"]]
            for group in response.context["tag_groups"]
        }
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.competencia, catalogs["competencias"])
        self.assertIn(self.estrategia, catalogs["estrategias"])
        self.assertIn(self.recurso, catalogs["recursos"])
        self.assertNotIn(other_competencia, catalogs["competencias"])
        self.assertNotIn(other_estrategia, catalogs["estrategias"])
        self.assertNotIn(other_recurso, catalogs["recursos"])
        self.assertContains(response, "data-chip-search")
        self.assertContains(response, "opción(es) de esta materia", count=3)

    def test_docente_topic_planning_adds_topic_to_class_with_another_topic(self):
        other_topic = Tema.objects.create(planificacion=self.planificacion, nombre="Geometria", orden=2)
        other_subtopic = Subtema.objects.create(tema=other_topic, nombre="Triangulos", orden=1)
        self.pendiente.tema = other_topic
        self.pendiente.save(update_fields=["tema"])
        self.pendiente.sync_subtemas_planificados([other_subtopic])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            {
                "tema_action": "assign",
                "clase_id": self.pendiente.pk,
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pendiente.tema, other_topic)
        self.assertEqual(self.pendiente.get_temas_planificados(), [other_topic, self.tema])
        self.assertEqual(self.pendiente.get_subtemas_planificados(), [other_subtopic])

    def test_docente_topic_planning_unassigns_draft_class(self):
        self.pendiente.tema = self.tema
        self.pendiente.subtema = self.subtema
        self.pendiente.save(update_fields=["tema", "subtema"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_tema_planificar", args=[self.planificacion_tema.pk]),
            {
                "tema_action": "unassign",
                "clase_id": self.pendiente.pk,
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.pendiente.tema)
        self.assertIsNone(self.pendiente.subtema)
        self.assertEqual(self.pendiente.get_subtemas_planificados(), [])

    def test_docente_class_planning_uses_single_class_docente_override(self):
        reemplazo, reemplazo_user = self.create_docente()
        self.pendiente.docente = reemplazo
        self.pendiente.docente_override = True
        self.pendiente.save(update_fields=["docente", "docente_override"])

        self.client.force_login(self.user)
        old_docente_response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            HTTP_HOST="localhost",
        )

        self.client.force_login(reemplazo_user)
        reemplazo_response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(old_docente_response.status_code, 404)
        self.assertEqual(reemplazo_response.status_code, 200)
        self.assertContains(reemplazo_response, "teacher-plan-hero")

    def test_docente_class_planning_draft_keeps_planification_pending(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            {
                "plan_action": "draft",
                "descripcion": "Borrador en progreso.",
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pendiente.estado_planificacion, "pendiente")
        self.assertEqual(self.pendiente.descripcion, "Borrador en progreso.")

    def test_docente_class_planning_send_requires_complete_content(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            {
                "plan_action": "send",
                "descripcion": "Solo detalle.",
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Selecciona el tema de la clase.")
        self.assertEqual(self.pendiente.estado_planificacion, "pendiente")

    def test_docente_class_planning_send_complete_content_to_review(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            {
                "plan_action": "send",
                "tema": self.tema.pk,
                "subtema": self.subtema.pk,
                "descripcion": "Desarrollo completo de la clase.",
                "competencias_existentes": [self.competencia.pk],
                "estrategias_existentes": [self.estrategia.pk],
                "recursos_existentes": [self.recurso.pk],
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pendiente.estado_planificacion, "revision")
        self.assertEqual(self.pendiente.tema, self.tema)
        self.assertEqual(self.pendiente.subtema, self.subtema)
        self.assertEqual(self.pendiente.get_subtemas_planificados(), [self.subtema])
        self.assertIn(self.competencia, self.pendiente.competencias.all())
        self.assertIn(self.estrategia, self.pendiente.estrategias.all())
        self.assertIn(self.recurso, self.pendiente.recursos.all())

    def test_docente_class_planning_saves_multiple_topics_and_their_subtopics(self):
        other_topic = Tema.objects.create(planificacion=self.planificacion, nombre="Geometria", orden=2)
        other_subtopic = Subtema.objects.create(tema=other_topic, nombre="Triangulos", orden=1)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            {
                "plan_action": "send",
                "temas_seleccionados": [self.tema.pk, other_topic.pk],
                "subtemas_seleccionados": [self.subtema.pk, other_subtopic.pk],
                "competencias_existentes": [self.competencia.pk],
                "estrategias_existentes": [self.estrategia.pk],
                "recursos_existentes": [self.recurso.pk],
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pendiente.get_temas_planificados(), [self.tema, other_topic])
        self.assertEqual(self.pendiente.get_subtemas_planificados(), [self.subtema, other_subtopic])
        self.assertEqual(self.pendiente.tema, self.tema)
        self.assertEqual(self.pendiente.subtema, self.subtema)

    def test_docente_class_planning_renders_open_multiple_academic_selectors(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            HTTP_HOST="localhost",
        )

        self.assertContains(response, "data-topic-dropdown")
        self.assertContains(response, "data-subtopic-dropdown")
        self.assertContains(response, 'name="temas_seleccionados"')
        self.assertContains(response, "Puedes repetirlos en otras clases")

    def test_docente_class_planning_creates_written_tags_and_subtopics(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            {
                "from_planificacion_tema": self.planificacion_tema.pk,
                "plan_action": "send",
                "tema": self.tema.pk,
                "subtemas_nuevos": "Terminos semejantes\nPolinomios",
                "competencias_nuevos": "Opera polinomios con precision",
                "estrategias_nuevos": "Ejercicios en parejas",
                "recursos_nuevos": "Guia impresa",
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pendiente.estado_planificacion, "revision")
        self.assertEqual(
            [subtema.nombre for subtema in self.pendiente.get_subtemas_planificados()],
            ["Terminos semejantes", "Polinomios"],
        )
        self.assertTrue(self.pendiente.competencias.filter(nombre="Opera polinomios con precision").exists())
        self.assertTrue(self.pendiente.estrategias.filter(nombre="Ejercicios en parejas").exists())
        self.assertTrue(self.pendiente.recursos.filter(nombre="Guia impresa").exists())
        self.assertTrue(
            self.pendiente.competencias.get(nombre="Opera polinomios con precision").materias.filter(
                pk=self.materia.pk
            ).exists()
        )
        self.assertTrue(
            self.pendiente.estrategias.get(nombre="Ejercicios en parejas").materias.filter(
                pk=self.materia.pk
            ).exists()
        )
        self.assertTrue(
            self.pendiente.recursos.get(nombre="Guia impresa").materias.filter(pk=self.materia.pk).exists()
        )

    def test_docente_class_planning_returns_to_topic_after_send(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            {
                "from_tema": self.tema.pk,
                "from_planificacion_tema": self.planificacion_tema.pk,
                "plan_action": "send",
                "tema": self.tema.pk,
                "subtema": self.subtema.pk,
                "descripcion": "Desarrollo completo de la clase.",
                "competencias_existentes": [self.competencia.pk],
                "estrategias_existentes": [self.estrategia.pk],
                "recursos_existentes": [self.recurso.pk],
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('academico:docente_tema_planificar', args=[self.planificacion_tema.pk])}#clase-{self.pendiente.pk}",
        )

    def test_docente_class_planning_creates_new_resource_with_file(self):
        self.client.force_login(self.user)
        uploaded = SimpleUploadedFile(
            "guia.pdf",
            b"contenido",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            {
                "plan_action": "send",
                "tema": self.tema.pk,
                "subtema": self.subtema.pk,
                "descripcion": "Desarrollo completo de la clase.",
                "competencias_existentes": [self.competencia.pk],
                "estrategias_existentes": [self.estrategia.pk],
                "recursos-TOTAL_FORMS": "1",
                "recursos-0-nombre": "Guia de ejercicios",
                "recursos-0-archivo": uploaded,
            },
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()
        recurso = Recurso.objects.get(nombre="Guia de ejercicios")
        clase_recurso = self.pendiente.clase_recursos.get(recurso=recurso)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pendiente.estado_planificacion, "revision")
        self.assertIn(recurso, self.pendiente.recursos.all())
        self.assertTrue(clase_recurso.archivo.name.endswith(".pdf"))

        response = self.client.get(
            reverse("academico:docente_clase_planificar", args=[self.pendiente.pk]),
            HTTP_HOST="localhost",
        )

        self.assertContains(response, "teacher-file-current")
        self.assertContains(response, "file-kind-pdf")
        self.assertContains(response, "ri-file-pdf-line")

    def test_docente_class_planning_approved_planification_is_locked(self):
        self.revision.estado_planificacion = "aprobada"
        self.revision.save(update_fields=["estado_planificacion"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("academico:docente_clase_planificar", args=[self.revision.pk]),
            {
                "plan_action": "send",
                "descripcion": "Cambio posterior.",
            },
            HTTP_HOST="localhost",
        )
        self.revision.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La planificacion aprobada no se puede editar")
        self.assertEqual(self.revision.estado_planificacion, "aprobada")
        self.assertEqual(self.revision.descripcion, "Clase enviada a revision.")

    def test_coordinacion_review_dashboard_filters_by_docente(self):
        coordinator = self.create_coordinator()
        self.client.force_login(coordinator)

        response = self.client.get(
            reverse("academico:coordinacion_revision_planificaciones"),
            {"docente": self.docente.pk, "estado": "revision"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enviadas")
        self.assertContains(response, "coordination-review-card")
        self.assertEqual(response.context["selected_docente"], self.docente)
        self.assertEqual(response.context["selected_estado"], "revision")
        self.assertEqual(len(response.context["revision_cards"]), 1)
        self.assertEqual(response.context["revision_cards"][0]["clase"], self.revision)

    def test_coordinacion_review_dashboard_shows_teacher_topic_and_subject_progress(self):
        otro_subtema = Subtema.objects.create(tema=self.tema, nombre="Resta", orden=2)
        self.revision.tema = self.tema
        self.revision.save(update_fields=["tema"])
        self.revision.sync_subtemas_planificados([self.subtema])
        coordinator = self.create_coordinator()
        self.client.force_login(coordinator)

        response = self.client.get(
            reverse("academico:coordinacion_revision_planificaciones"),
            {"docente": self.docente.pk, "estado": "revision"},
            HTTP_HOST="localhost",
        )
        card = response.context["revision_cards"][0]

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Historial del docente")
        self.assertContains(response, "Avance tema")
        self.assertContains(response, "Avance materia")
        self.assertEqual(card["topic_progress"]["covered"], 1)
        self.assertEqual(card["topic_progress"]["total"], 2)
        self.assertEqual(card["topic_progress"]["progress"], 50)
        self.assertEqual(card["materia_progress"]["covered"], 1)
        self.assertEqual(card["materia_progress"]["total"], 2)
        self.assertEqual(card["materia_progress"]["progress"], 50)
        self.assertEqual(response.context["docente_history"]["progress"]["progress"], 50)
        self.assertIn(otro_subtema, list(self.tema.subtemas_planificacion.all()))

    def test_coordinacion_review_dashboard_filters_by_docente_override(self):
        coordinator = self.create_coordinator()
        reemplazo, _ = self.create_docente()
        self.pendiente.docente = reemplazo
        self.pendiente.docente_override = True
        self.pendiente.save(update_fields=["docente", "docente_override"])
        self.client.force_login(coordinator)

        response = self.client.get(
            reverse("academico:coordinacion_revision_planificaciones"),
            {"docente": reemplazo.pk, "estado": "pendiente"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_docente"], reemplazo)
        self.assertEqual(len(response.context["revision_cards"]), 1)
        self.assertEqual(response.context["revision_cards"][0]["clase"], self.pendiente)

    def test_coordinacion_review_dashboard_shows_late_cards(self):
        coordinator = self.create_coordinator()
        self.client.force_login(coordinator)

        response = self.client.get(
            reverse("academico:coordinacion_revision_planificaciones"),
            {"docente": self.docente.pk, "estado": "atrasadas"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Atrasada")
        self.assertEqual(response.context["selected_estado"], "atrasadas")
        self.assertEqual(len(response.context["revision_cards"]), 1)
        self.assertEqual(response.context["revision_cards"][0]["clase"], self.atrasada)

    def test_coordinacion_attendance_review_filters_by_group_and_docente(self):
        coordinator = self.create_coordinator()
        estudiante_uno, ficha_uno = self.create_student_ficha(
            nombre="Ana Asistencia",
            identificacion="AST-001",
            numero="AST-001",
        )
        estudiante_dos, ficha_dos = self.create_student_ficha(
            nombre="Luis Asistencia",
            identificacion="AST-002",
            numero="AST-002",
        )
        GrupoEstudiante.objects.create(ficha_inscripcion=ficha_uno, estudiante=estudiante_uno, grupo=self.curso)
        GrupoEstudiante.objects.create(ficha_inscripcion=ficha_dos, estudiante=estudiante_dos, grupo=self.curso)
        ClaseAsistencia.objects.create(
            clase=self.revision,
            estudiante=estudiante_uno,
            estado="presente",
            registrado_por=self.docente,
        )
        ClaseAsistencia.objects.create(
            clase=self.revision,
            estudiante=estudiante_dos,
            estado="ausente",
            observacion="No asistio.",
            registrado_por=self.docente,
        )
        self.client.force_login(coordinator)

        response = self.client.get(
            reverse("academico:coordinacion_revision_asistencia"),
            {"grupo": self.curso.pk, "docente": self.docente.pk, "estado": "ausentes"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revision de asistencia")
        self.assertContains(response, "attendance-review-card")
        self.assertContains(response, "Ver reporte")
        self.assertNotContains(response, "Ana Asistencia")
        self.assertNotContains(response, "No asistio.")
        self.assertEqual(response.context["selected_grupo"], self.curso)
        self.assertEqual(response.context["selected_docente"], self.docente)
        self.assertEqual(response.context["selected_estado"], "ausentes")
        self.assertEqual(len(response.context["attendance_cards"]), 1)
        card = response.context["attendance_cards"][0]
        self.assertEqual(card["clase"], self.revision)
        self.assertEqual(card["counts"]["presente"], 1)
        self.assertEqual(card["counts"]["ausente"], 1)
        self.assertEqual(card["observation_count"], 1)

        report_response = self.client.get(str(card["report_url"]), HTTP_HOST="localhost")

        self.assertEqual(report_response.status_code, 200)
        self.assertContains(report_response, "Reporte de asistencia")
        self.assertContains(report_response, "Ana Asistencia")
        self.assertContains(report_response, "No asistio.")
        self.assertEqual(report_response.context["card"]["counts"]["ausente"], 1)

    def test_coordinacion_class_attendance_report_shows_last_names_before_names(self):
        coordinator = self.create_coordinator()
        estudiante_zambrano, ficha_zambrano = self.create_student_ficha(
            nombre="María Fernanda",
            apellido="Zambrano López",
            identificacion="AST-NAME-001",
            numero="AST-NAME-001",
        )
        estudiante_alvarez, ficha_alvarez = self.create_student_ficha(
            nombre="Carlos Andrés",
            apellido="Álvarez Pérez",
            identificacion="AST-NAME-002",
            numero="AST-NAME-002",
        )
        GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha_zambrano,
            estudiante=estudiante_zambrano,
            grupo=self.curso,
        )
        GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha_alvarez,
            estudiante=estudiante_alvarez,
            grupo=self.curso,
        )
        self.client.force_login(coordinator)

        response = self.client.get(
            reverse("academico:coordinacion_reporte_asistencia_clase", args=[self.revision.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Álvarez Pérez Carlos Andrés")
        self.assertContains(response, "Zambrano López María Fernanda")
        self.assertEqual(
            [row["estudiante_apellidos_nombres"] for row in response.context["card"]["fichas"]],
            ["Álvarez Pérez Carlos Andrés", "Zambrano López María Fernanda"],
        )

    def test_closed_attendance_with_all_students_registered_is_complete(self):
        coordinator = self.create_coordinator()
        estudiante, ficha = self.create_student_ficha(
            nombre="Clase Cerrada",
            identificacion="CER-001",
            numero="CER-001",
        )
        GrupoEstudiante.objects.create(ficha_inscripcion=ficha, estudiante=estudiante, grupo=self.curso)
        ClaseAsistencia.objects.create(
            clase=self.revision,
            estudiante=estudiante,
            estado="presente",
            registrado_por=self.docente,
        )
        self.revision.asistencia_cerrada = True
        self.revision.fecha_cierre_asistencia = timezone.now()
        self.revision.save(update_fields=["asistencia_cerrada", "fecha_cierre_asistencia"])
        self.client.force_login(coordinator)

        response = self.client.get(
            reverse("academico:coordinacion_revision_asistencia"),
            {"grupo": self.curso.pk, "docente": self.docente.pk, "estado": "cerradas"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["attendance_cards"]), 1)
        card = response.context["attendance_cards"][0]
        self.assertEqual(card["status_key"], "completa")
        self.assertEqual(card["status_label"], "Completa")
        self.assertEqual(response.context["attendance_stats"]["clases_completas"], 1)
        self.assertContains(response, "Completa")
        self.assertContains(response, "Asistencias tomadas")
        self.assertContains(response, "1 de 4")
        self.assertContains(response, "ri-lock-2-line")

        taken_response = self.client.get(response.context["taken_filter_url"], HTTP_HOST="localhost")

        self.assertEqual(taken_response.status_code, 200)
        self.assertEqual(taken_response.context["selected_estado"], "tomadas")
        self.assertEqual(taken_response.context["selected_estado_label"], "Asistencias tomadas")
        self.assertEqual(len(taken_response.context["attendance_cards"]), 1)
        self.assertEqual(taken_response.context["attendance_cards"][0]["clase"], self.revision)

    def test_attendance_cards_load_rosters_in_constant_queries(self):
        view = CoordinacionRevisionAsistenciaView()

        with self.assertNumQueries(5):
            clases = list(view.get_clases_queryset().distinct())
            roster_data = view.get_roster_data(clases)
            cards = [view.build_attendance_card(clase, roster_data=roster_data) for clase in clases]

        self.assertEqual(len(cards), 4)

    def test_coordinacion_student_attendance_report_exports_parent_excel(self):
        coordinator = self.create_coordinator()
        estudiante_uno, ficha_uno = self.create_student_ficha(
            nombre="Ana Padres",
            identificacion="PAD-001",
            numero="PAD-001",
        )
        estudiante_dos, ficha_dos = self.create_student_ficha(
            nombre="Luis Padres",
            identificacion="PAD-002",
            numero="PAD-002",
        )
        GrupoEstudiante.objects.create(ficha_inscripcion=ficha_uno, estudiante=estudiante_uno, grupo=self.curso)
        GrupoEstudiante.objects.create(ficha_inscripcion=ficha_dos, estudiante=estudiante_dos, grupo=self.curso)
        ClaseAsistencia.objects.create(
            clase=self.revision,
            estudiante=estudiante_uno,
            estado="ausente",
            observacion="No asistio por cita medica.",
            registrado_por=self.docente,
        )
        ClaseAsistencia.objects.create(
            clase=self.revision,
            estudiante=estudiante_dos,
            estado="presente",
            observacion="Otro alumno.",
            registrado_por=self.docente,
        )
        params = {
            "grupo": self.curso.pk,
            "estudiante": estudiante_uno.pk,
            "desde": self.pendiente.fecha.isoformat(),
            "hasta": self.revision.fecha.isoformat(),
        }
        self.client.force_login(coordinator)

        response = self.client.get(reverse("academico:coordinacion_reporte_asistencia_alumno"), params, HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reporte de asistencia del alumno")
        self.assertContains(response, "Ana Padres")
        self.assertContains(response, "Matematicas")
        self.assertContains(response, "No asistio por cita medica.")
        self.assertNotContains(response, "Otro alumno.")
        self.assertEqual(response.context["stats"]["total"], 2)
        self.assertEqual(response.context["stats"]["ausente"], 1)
        self.assertEqual(response.context["stats"]["pendiente"], 1)
        self.assertFalse(
            any(row["observacion"] == "Otro alumno." for row in response.context["rows"])
        )

        export_response = self.client.get(
            reverse("academico:coordinacion_reporte_asistencia_alumno"),
            {**params, "export": "excel"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(
            export_response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        workbook = load_workbook(BytesIO(export_response.content))
        sheet = workbook.active
        values = [cell.value for row in sheet.iter_rows() for cell in row if cell.value]

        self.assertIn("Reporte de asistencia del alumno", values)
        self.assertIn("Ana Padres", values)
        self.assertIn("Matematicas", values)
        self.assertIn("Ausente", values)
        self.assertIn("No asistio por cita medica.", values)
        self.assertNotIn("Luis Padres", values)

    def test_director_attendance_review_opens_without_docente_partner(self):
        director = get_user_model().objects.create_user(username="director-asistencia", password="ClaveActual987!")
        director.groups.add(Group.objects.get_or_create(name="Director")[0])
        estudiante, ficha = self.create_student_ficha()
        GrupoEstudiante.objects.create(
            ficha_inscripcion=ficha,
            estudiante=estudiante,
            grupo=self.curso,
            fecha_asignacion=self.atrasada.fecha,
        )
        self.client.force_login(director)

        response = self.client.get(
            reverse("academico:coordinacion_revision_asistencia"),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revision de asistencia")
        self.assertContains(response, "Revision asistencia")
        self.assertGreaterEqual(response.context["attendance_stats"]["total"], 4)
        self.assertGreaterEqual(response.context["attendance_stats"]["pendientes_registro"], 4)

    def test_director_can_register_teacher_replacement_hours(self):
        director = self.create_director()
        reemplazo, _ = self.create_docente()
        clase = self.create_class_for_date(timezone.localdate(), time(10, 0), time(12, 0), aula_nombre="Aula pago")
        self.client.force_login(director)

        response = self.client.post(
            reverse("academico:direccion_horas_docente"),
            {
                "fecha": clase.fecha.isoformat(),
                "clase": clase.pk,
                f"hora_{clase.pk}-estado": "reemplazo",
                f"hora_{clase.pk}-docente": reemplazo.pk,
                f"hora_{clase.pk}-horas": "1",
                f"hora_{clase.pk}-minutos": "50",
                f"hora_{clase.pk}-observacion": "Reemplazo autorizado.",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        registro = ClaseHoraDocente.objects.get(clase=clase)
        self.assertEqual(registro.estado, "reemplazo")
        self.assertEqual(registro.docente, reemplazo)
        self.assertEqual(registro.docente_reemplazado, self.docente)
        self.assertEqual(registro.horas, Decimal("1.50"))
        self.assertEqual(registro.registrado_por, director)

    def test_unregistered_teacher_hours_start_pending_and_zero(self):
        director = self.create_director()
        clase = self.create_class_for_date(
            timezone.localdate(),
            time(10, 0),
            time(13, 0),
            aula_nombre="Aula horas manuales",
        )
        self.client.force_login(director)

        response = self.client.get(
            reverse("academico:direccion_horas_docente"),
            {"fecha": clase.fecha.isoformat()},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.context["rows"] if item["clase"] == clase)
        self.assertIsNone(row["registro"])
        self.assertEqual(row["form"]["estado"].value(), "pendiente")
        self.assertEqual(row["form"]["horas"].value(), 0)
        self.assertEqual(row["form"]["minutos"].value(), 0)
        self.assertEqual(row["horas_programadas"], Decimal("3.00"))
        self.assertContains(response, "Las horas no se cargan automáticamente")
        self.assertFalse(ClaseHoraDocente.objects.filter(clase=clase).exists())

    def test_teacher_hours_use_hours_and_minutes_and_normalize_totals(self):
        director = self.create_director()
        first_class = self.create_class_for_date(
            timezone.localdate(),
            time(10, 0),
            time(13, 0),
            aula_nombre="Aula duracion uno",
        )
        second_class = self.create_class_for_date(
            timezone.localdate(),
            time(14, 0),
            time(15, 0),
            aula_nombre="Aula duracion dos",
        )
        self.client.force_login(director)

        for clase, hours, minutes in ((first_class, "1", "50"), (second_class, "0", "20")):
            response = self.client.post(
                reverse("academico:direccion_horas_docente"),
                {
                    "fecha": clase.fecha.isoformat(),
                    "clase": clase.pk,
                    f"hora_{clase.pk}-estado": "asistio",
                    f"hora_{clase.pk}-horas": hours,
                    f"hora_{clase.pk}-minutos": minutes,
                },
                HTTP_HOST="localhost",
            )
            self.assertEqual(response.status_code, 302)

        self.assertEqual(ClaseHoraDocente.objects.get(clase=first_class).horas, Decimal("1.50"))
        self.assertEqual(ClaseHoraDocente.objects.get(clase=second_class).horas, Decimal("0.20"))

        report_response = self.client.get(
            reverse("academico:direccion_horas_docente_reporte"),
            {
                "desde": first_class.fecha.isoformat(),
                "hasta": first_class.fecha.isoformat(),
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(report_response.context["stats"]["horas"], Decimal("2.10"))
        self.assertEqual(report_response.context["stats"]["horas_label"], "2:10")
        self.assertContains(report_response, "1:50")
        self.assertContains(report_response, "0:20")

    def test_existing_teacher_hours_are_split_into_hours_and_minutes_fields(self):
        director = self.create_director()
        clase = self.create_class_for_date(
            timezone.localdate(),
            time(10, 0),
            time(12, 0),
            aula_nombre="Aula horas existentes",
        )
        ClaseHoraDocente.objects.create(
            clase=clase,
            docente=self.docente,
            estado="asistio",
            horas=Decimal("1.50"),
            registrado_por=director,
            fecha_registro=timezone.now(),
            usuario_updated=director,
        )
        self.client.force_login(director)

        response = self.client.get(
            reverse("academico:direccion_horas_docente"),
            {"fecha": clase.fecha.isoformat()},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.context["rows"] if item["clase"] == clase)
        self.assertEqual(row["form"]["horas"].value(), 1)
        self.assertEqual(row["form"]["minutos"].value(), 50)

    def test_teacher_hours_reject_minutes_greater_than_fifty_nine(self):
        director = self.create_director()
        clase = self.create_class_for_date(
            timezone.localdate(),
            time(10, 0),
            time(13, 0),
            aula_nombre="Aula duracion invalida",
        )
        self.client.force_login(director)

        response = self.client.post(
            reverse("academico:direccion_horas_docente"),
            {
                "fecha": clase.fecha.isoformat(),
                "clase": clase.pk,
                f"hora_{clase.pk}-estado": "asistio",
                f"hora_{clase.pk}-horas": "1",
                f"hora_{clase.pk}-minutos": "75",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Los minutos deben estar entre 00 y 59")
        self.assertFalse(ClaseHoraDocente.objects.filter(clase=clase).exists())

    def test_teacher_hours_asistio_ignores_posted_replacement_teacher(self):
        director = self.create_director()
        reemplazo, _ = self.create_docente()
        clase = self.create_class_for_date(timezone.localdate(), time(10, 0), time(12, 0), aula_nombre="Aula pago")
        self.client.force_login(director)

        response = self.client.post(
            reverse("academico:direccion_horas_docente"),
            {
                "fecha": clase.fecha.isoformat(),
                "clase": clase.pk,
                f"hora_{clase.pk}-estado": "asistio",
                f"hora_{clase.pk}-docente": reemplazo.pk,
                f"hora_{clase.pk}-horas": "2",
                f"hora_{clase.pk}-minutos": "0",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        registro = ClaseHoraDocente.objects.get(clase=clase)
        self.assertEqual(registro.estado, "asistio")
        self.assertEqual(registro.docente, self.docente)
        self.assertIsNone(registro.docente_reemplazado)

    def test_docente_cannot_open_director_teacher_hours(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("academico:direccion_horas_docente"),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 403)

    def test_coordinator_cannot_open_director_teacher_hours(self):
        self.client.force_login(self.create_coordinator())

        response = self.client.get(
            reverse("academico:direccion_horas_docente"),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 403)

    def test_teacher_hours_access_permission_can_be_assigned_read_only_to_group(self):
        user = get_user_model().objects.create_user(username="consulta-horas", password="ClaveActual987!")
        group = Group.objects.create(name="Consulta horas docente")
        group.permissions.add(Permission.objects.get(codename="access_clasehoradocente"))
        user.groups.add(group)
        clase = self.create_class_for_date(
            timezone.localdate(),
            time(10, 0),
            time(11, 0),
            aula_nombre="Aula consulta horas",
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("academico:direccion_horas_docente"),
            {"fecha": clase.fecha.isoformat()},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Consulta de solo lectura")
        self.assertNotContains(response, '<form class="teacher-hour-form"')
        self.assertNotContains(response, ">Reporte<", html=True)

        post_response = self.client.post(
            reverse("academico:direccion_horas_docente"),
            {
                "fecha": clase.fecha.isoformat(),
                "clase": clase.pk,
                f"hora_{clase.pk}-estado": "asistio",
                f"hora_{clase.pk}-horas": "1",
                f"hora_{clase.pk}-minutos": "0",
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(post_response.status_code, 403)
        self.assertFalse(ClaseHoraDocente.objects.filter(clase=clase).exists())

    def test_teacher_hours_report_renders_and_exports_excel(self):
        director = self.create_director()
        clase = self.create_class_for_date(timezone.localdate(), time(14, 0), time(16, 0), aula_nombre="Aula reporte")
        ClaseHoraDocente.objects.create(
            clase=clase,
            docente=self.docente,
            estado="asistio",
            horas=Decimal("2.00"),
            registrado_por=director,
            fecha_registro=timezone.now(),
            usuario_updated=director,
        )
        self.client.force_login(director)
        params = {
            "desde": clase.fecha.isoformat(),
            "hasta": clase.fecha.isoformat(),
        }

        response = self.client.get(
            reverse("academico:direccion_horas_docente_reporte"),
            params,
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reporte horas docente")
        self.assertContains(response, "Docente Prueba")
        self.assertEqual(response.context["stats"]["horas"], Decimal("2.00"))

        export_response = self.client.get(
            reverse("academico:direccion_horas_docente_reporte"),
            {**params, "export": "excel"},
            HTTP_HOST="localhost",
        )

        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(
            export_response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        workbook = load_workbook(BytesIO(export_response.content))
        values = [cell.value for row in workbook.active.iter_rows() for cell in row if cell.value]
        self.assertIn("Docente Prueba", values)
        self.assertIn("Matematicas", values)
        self.assertIn(2, values)

    def test_coordinacion_review_detail_denies_user_without_review_permission(self):
        self.client.force_login(self.user)
        url = reverse("academico:coordinacion_revision_planificacion_detalle", args=[self.revision.pk])
        self.assertEqual(self.client.get(url, HTTP_HOST="localhost").status_code, 403)
        self.assertEqual(self.client.post(url, {"review_action": "aprobar"}, HTTP_HOST="localhost").status_code, 403)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.estado_planificacion, "revision")

    def test_coordinacion_review_detail_renders_visual_review_panel(self):
        coordinator = self.create_coordinator()
        self.client.force_login(coordinator)

        response = self.client.get(
            reverse("academico:coordinacion_revision_planificacion_detalle", args=[self.revision.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "review-hero-panel")
        self.assertContains(response, "Checklist de revision")
        self.assertContains(response, "review-decision-panel")
        self.assertEqual(response.context["review_total"], 4)

    def test_coordinacion_review_detail_shows_topic_and_subject_progress(self):
        Subtema.objects.create(tema=self.tema, nombre="Resta", orden=2)
        self.revision.tema = self.tema
        self.revision.save(update_fields=["tema"])
        self.revision.sync_subtemas_planificados([self.subtema])
        coordinator = self.create_coordinator()
        self.client.force_login(coordinator)

        response = self.client.get(
            reverse("academico:coordinacion_revision_planificacion_detalle", args=[self.revision.pk]),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Avance del tema")
        self.assertContains(response, "Avance de la materia")
        self.assertEqual(response.context["topic_progress"]["progress"], 50)
        self.assertEqual(response.context["materia_progress"]["progress"], 50)

    def test_coordinacion_review_detail_approval_requires_all_sections_checked(self):
        coordinator = self.create_coordinator()
        self.client.force_login(coordinator)

        response = self.client.post(
            reverse("academico:coordinacion_revision_planificacion_detalle", args=[self.revision.pk]),
            {"review_action": "aprobar"},
            HTTP_HOST="localhost",
        )
        self.revision.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Marca todos los puntos como correctos")
        self.assertEqual(self.revision.estado_planificacion, "revision")

    def test_coordinacion_review_detail_rejects_one_observed_section(self):
        coordinator = self.create_coordinator()
        self.client.force_login(coordinator)

        response = self.client.post(
            reverse("academico:coordinacion_revision_planificacion_detalle", args=[self.revision.pk]),
            {
                "review_action": "rechazar",
                "notas_revision": "Corregir recursos.",
                "revision_tema_ok": "on",
                "revision_competencias_ok": "on",
                "revision_estrategias_ok": "on",
                "observacion_recursos": "Agregar un recurso verificable.",
            },
            HTTP_HOST="localhost",
        )
        self.revision.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.revision.estado_planificacion, "rechazada")
        self.assertFalse(self.revision.revision_recursos_ok)
        self.assertEqual(
            self.revision.observaciones_revision,
            {"recursos": "Agregar un recurso verificable."},
        )
