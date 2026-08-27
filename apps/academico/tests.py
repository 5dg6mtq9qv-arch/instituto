import json
import shutil
import tempfile
from datetime import timedelta, time
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from apps.academico.models import (
    Aula,
    AulaCurso,
    Clase,
    Competencia,
    Curso,
    CursoPeriodo,
    Dia,
    Estrategia,
    Horario,
    HorarioAulaCurso,
    HorarioDia,
    Materia,
    MateriaCurso,
    Periodo,
    PlanificacionDocente,
    ProfesorMateriaCurso,
    Recurso,
    Subtema,
    Tema,
)
from apps.core.current_user import set_current_request
from apps.core.models import Partner, TipoIdentificacion


class DocenteHorariosPanelTests(TestCase):
    def setUp(self):
        set_current_request(None)
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.user = get_user_model().objects.create_user(username="docente", password="ClaveActual987!")
        tipo_identificacion = TipoIdentificacion.objects.create(nombre="Cedula", codigo="CED")
        self.docente = Partner.objects.create(
            tipo_identificacion=tipo_identificacion,
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
        ProfesorMateriaCurso.objects.create(partner=self.docente, materia_curso=self.materia_curso)
        self.planificacion = PlanificacionDocente.objects.create(
            materia_curso=self.materia_curso,
            nombre="Plan base",
        )
        self.tema = Tema.objects.create(planificacion=self.planificacion, nombre="Numeros", orden=1)
        self.subtema = Subtema.objects.create(tema=self.tema, nombre="Suma", orden=1)
        self.competencia = Competencia.objects.create(nombre="Resolver problemas")
        self.estrategia = Estrategia.objects.create(nombre="Aprendizaje guiado")
        self.recurso = Recurso.objects.create(nombre="Pizarra")
        today = timezone.localdate()
        self.pendiente = Clase.objects.create(
            horario_aula_curso=self.horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=today + timedelta(days=4),
            estado_planificacion="pendiente",
        )
        self.revision = Clase.objects.create(
            horario_aula_curso=self.horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=today + timedelta(days=11),
            estado_planificacion="revision",
            descripcion="Clase enviada a revision.",
        )
        self.rechazada = Clase.objects.create(
            horario_aula_curso=self.horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=today + timedelta(days=18),
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

    def create_coordinator(self):
        user = get_user_model().objects.create_user(username="coordinador", password="ClaveActual987!")
        user.groups.add(Group.objects.get_or_create(name="Coordinacion")[0])
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

    def test_docente_dashboard_renders_panel_cards(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("academico:docente_horarios"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mis planificaciones")
        self.assertContains(response, "Por atender")
        self.assertContains(response, "docente-planning-card")
        self.assertEqual(response.context["planificacion_stats"]["total"], 4)
        self.assertEqual(response.context["planificacion_stats"]["por_atender"], 3)

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

        self.assertTrue(any("Matematicas" in str(value) for value in values))
        self.assertTrue(any("Grupo A" in str(value) for value in values))

    def test_academic_planning_updates_future_class_without_delete_error(self):
        self.create_periodo_for_course()
        self.make_superuser()
        self.pendiente.tema = self.tema
        self.pendiente.subtema = self.subtema
        self.pendiente.descripcion = "Planificacion previa."
        self.pendiente.estado_planificacion = "revision"
        self.pendiente.save(update_fields=["tema", "subtema", "descripcion", "estado_planificacion"])
        self.pendiente.competencias.add(self.competencia)
        self.pendiente.estrategias.add(self.estrategia)
        self.pendiente.recursos.add(self.recurso)
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
            HTTP_HOST="localhost",
        )
        self.pendiente.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pendiente.materia_curso.materia, nueva_materia)
        self.assertEqual(self.pendiente.estado_planificacion, "pendiente")
        self.assertIsNone(self.pendiente.tema)
        self.assertFalse(self.pendiente.recursos.exists())

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
        self.assertContains(response, "La clase no se puede modificar porque tiene una planificacion aprobada.")
        self.assertContains(response, "approved-locked-event")

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
        self.assertContains(response, "Usar disponible")
        self.assertContains(response, "Crear nuevo")
        self.assertContains(response, "data-available-select")
        self.assertContains(response, "data-selected-list")
        self.assertEqual(response.context["planning_total"], 5)

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
        self.assertIn(self.competencia, self.pendiente.competencias.all())
        self.assertIn(self.estrategia, self.pendiente.estrategias.all())
        self.assertIn(self.recurso, self.pendiente.recursos.all())

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
        self.assertEqual(response.context["review_total"], 5)

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
                "notas_revision": "Corregir detalle.",
                "revision_tema_ok": "on",
                "revision_competencias_ok": "on",
                "revision_estrategias_ok": "on",
                "revision_recursos_ok": "on",
                "observacion_detalle": "Ampliar la explicacion de la clase.",
            },
            HTTP_HOST="localhost",
        )
        self.revision.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.revision.estado_planificacion, "rechazada")
        self.assertFalse(self.revision.revision_detalle_ok)
        self.assertEqual(
            self.revision.observaciones_revision,
            {"detalle": "Ampliar la explicacion de la clase."},
        )
