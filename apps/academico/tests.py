from datetime import timedelta, time

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.academico.models import (
    Aula,
    AulaCurso,
    Clase,
    Competencia,
    Curso,
    Dia,
    Estrategia,
    Horario,
    HorarioAulaCurso,
    HorarioDia,
    Materia,
    MateriaCurso,
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
        curso = Curso.objects.create(nombre="Grupo A", activo=True)
        aula = Aula.objects.create(nombre="Aula 1")
        aula_curso = AulaCurso.objects.create(aula=aula, curso=curso)
        dia, _ = Dia.objects.get_or_create(dia="Lunes")
        horario = Horario.objects.create(hora_inicio=time(8, 0), hora_fin=time(9, 0))
        horario_dia = HorarioDia.objects.create(dia=dia, horario=horario)
        horario_aula_curso = HorarioAulaCurso.objects.create(aula_curso=aula_curso, horario_dia=horario_dia)
        materia = Materia.objects.create(nombre="Matematicas", nombre_corto="MAT", color="#0f766e")
        self.materia_curso = MateriaCurso.objects.create(materia=materia, grupo=curso)
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
            horario_aula_curso=horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=today + timedelta(days=4),
            estado_planificacion="pendiente",
        )
        self.revision = Clase.objects.create(
            horario_aula_curso=horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=today + timedelta(days=11),
            estado_planificacion="revision",
            descripcion="Clase enviada a revision.",
        )
        self.rechazada = Clase.objects.create(
            horario_aula_curso=horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=today + timedelta(days=18),
            estado_planificacion="rechazada",
            descripcion="Clase con observaciones.",
            notas_revision="Completar recursos.",
        )
        self.atrasada = Clase.objects.create(
            horario_aula_curso=horario_aula_curso,
            materia_curso=self.materia_curso,
            fecha=today - timedelta(days=1),
            estado_planificacion="pendiente",
        )

    def tearDown(self):
        set_current_request(None)

    def create_coordinator(self):
        user = get_user_model().objects.create_user(username="coordinador", password="ClaveActual987!")
        user.groups.add(Group.objects.get_or_create(name="Coordinacion")[0])
        return user

    def test_docente_dashboard_renders_panel_cards(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("academico:docente_horarios"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mis planificaciones")
        self.assertContains(response, "Por atender")
        self.assertContains(response, "docente-planning-card")
        self.assertEqual(response.context["planificacion_stats"]["total"], 4)
        self.assertEqual(response.context["planificacion_stats"]["por_atender"], 3)

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
