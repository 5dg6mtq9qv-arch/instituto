"""Métricas mensuales consolidadas por docente para Coordinación."""

from collections import defaultdict

from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.core.models import Partner

from .models import (
    Clase,
    ClaseAsistencia,
    GrupoEstudiante,
    MoodleCalificacion,
    MoodleMatricula,
    ProfesorMateriaCurso,
    Subtema,
)


PLAN_STATES = ("pendiente", "revision", "rechazada", "aprobada")


def percent(done, total):
    return round((done / total) * 100, 1) if total else None


def class_teachers(clase):
    if clase.docente_override:
        return [clase.docente] if clase.docente_id else []
    return [
        assignment.partner
        for assignment in clase.materia_curso.profesor_materia_cursos.all()
        if not assignment.auto_generada_por_clases
    ]


def class_subtopic_ids(clase):
    ids = {item.subtema_id for item in clase.clase_subtemas.all()}
    if not ids and clase.subtema_id:
        ids.add(clase.subtema_id)
    return ids


def empty_metrics():
    return {
        "scheduled": 0,
        "attended": 0,
        "absent": 0,
        "replaced": 0,
        "replacements_given": 0,
        "suspended": 0,
        "teacher_pending": 0,
        "attendance_closed_classes": 0,
        "student_present": 0,
        "student_late": 0,
        "student_absent": 0,
        "student_justified": 0,
        "plan": {state: 0 for state in PLAN_STATES},
        "plan_late": 0,
        "monthly_subtopics": set(),
        "covered_subtopics": set(),
        "total_subtopics": set(),
        "virtual_expected": 0,
        "virtual_confirmed": 0,
        "grade_students": 0,
        "grade_expected_students": 0,
        "grade_activities": 0,
        "grade_student_values": [],
    }


def empty_teacher_row(teacher):
    return {
        "teacher": teacher,
        "metrics": empty_metrics(),
        "subjects": {},
    }


def subject_metrics(clase):
    metrics = empty_metrics()
    metrics.update(
        {
            "materia_curso": clase.materia_curso,
            "materia": clase.materia_curso.materia,
            "grupo": clase.materia_curso.grupo,
        }
    )
    return metrics


def add_class_metrics(metrics, clase, teacher, today):
    metrics["scheduled"] += 1
    metrics["plan"][clase.estado_planificacion] += 1
    if clase.fecha < today and clase.estado_planificacion in {"pendiente", "rechazada"}:
        metrics["plan_late"] += 1

    try:
        teacher_hours = clase.hora_docente
    except Clase.hora_docente.RelatedObjectDoesNotExist:
        teacher_hours = None

    if not teacher_hours or teacher_hours.estado == "pendiente":
        metrics["teacher_pending"] += 1
    elif teacher_hours.estado == "suspendida":
        metrics["suspended"] += 1
    elif teacher_hours.estado == "no_asistio":
        metrics["absent"] += 1
    elif teacher_hours.estado == "reemplazo":
        metrics["replaced"] += 1
    elif teacher_hours.estado == "asistio" and teacher_hours.docente_id == teacher.pk:
        metrics["attended"] += 1

    if clase.asistencia_cerrada:
        metrics["attendance_closed_classes"] += 1
        attendance_keys = {
            "presente": "student_present",
            "atraso": "student_late",
            "ausente": "student_absent",
            "justificado": "student_justified",
        }
        for attendance in clase.asistencias_clase.all():
            key = attendance_keys.get(attendance.estado)
            if key in metrics:
                metrics[key] += 1

    if clase.estado_planificacion == "aprobada":
        metrics["monthly_subtopics"].update(class_subtopic_ids(clase))


def finalize_metrics(metrics):
    teacher_denominator = metrics["scheduled"] - metrics["suspended"]
    student_denominator = (
        metrics["student_present"] + metrics["student_late"] + metrics["student_absent"]
    )
    metrics["teacher_attendance_percent"] = percent(metrics["attended"], teacher_denominator)
    metrics["student_attendance_percent"] = percent(
        metrics["student_present"] + metrics["student_late"], student_denominator
    )
    metrics["virtual_percent"] = percent(metrics["virtual_confirmed"], metrics["virtual_expected"])
    metrics["topic_percent"] = percent(
        len(metrics["covered_subtopics"]), len(metrics["total_subtopics"])
    )
    metrics["monthly_subtopics_count"] = len(metrics["monthly_subtopics"])
    metrics["covered_subtopics_count"] = len(metrics["covered_subtopics"])
    metrics["total_subtopics_count"] = len(metrics["total_subtopics"])
    metrics["plan_approval_percent"] = percent(metrics["plan"]["aprobada"], metrics["scheduled"])
    metrics["grade_coverage_percent"] = percent(
        metrics["grade_students"], metrics["grade_expected_students"]
    )
    values = metrics.pop("grade_student_values")
    metrics["grade_average"] = round(sum(values) / len(values), 1) if values else None
    return metrics


def build_monthly_teacher_report(start, end, cutoff, selected_teacher=None):
    """Devuelve filas comparables y desglose por asignatura hasta la fecha de corte."""
    teacher_prefetch = Prefetch(
        "materia_curso__profesor_materia_cursos",
        queryset=ProfesorMateriaCurso.objects.select_related("partner"),
    )
    classes = list(
        Clase.objects.filter(fecha__gte=start, fecha__lte=cutoff)
        .select_related(
            "docente",
            "hora_docente__docente",
            "hora_docente__docente_reemplazado",
            "materia_curso__materia",
            "materia_curso__grupo",
            "subtema",
        )
        .prefetch_related(
            teacher_prefetch,
            "clase_subtemas",
            Prefetch("asistencias_clase", queryset=ClaseAsistencia.objects.only("clase_id", "estado")),
        )
        .order_by("fecha", "pk")
    ) if cutoff >= start else []

    rows = {}

    def row_for(teacher):
        if selected_teacher and teacher.pk != selected_teacher.pk:
            return None
        return rows.setdefault(teacher.pk, empty_teacher_row(teacher))

    if selected_teacher:
        row_for(selected_teacher)

    today = timezone.localdate()
    for clase in classes:
        scheduled_teachers = class_teachers(clase)
        for teacher in scheduled_teachers:
            row = row_for(teacher)
            if row is None:
                continue
            detail = row["subjects"].setdefault(clase.materia_curso_id, subject_metrics(clase))
            add_class_metrics(row["metrics"], clase, teacher, today)
            add_class_metrics(detail, clase, teacher, today)

        try:
            teacher_hours = clase.hora_docente
        except Clase.hora_docente.RelatedObjectDoesNotExist:
            teacher_hours = None
        if teacher_hours and teacher_hours.estado == "reemplazo" and teacher_hours.docente:
            replacement_row = row_for(teacher_hours.docente)
            if replacement_row is not None:
                replacement_row["metrics"]["replacements_given"] += 1

    course_ids = {
        course_id
        for row in rows.values()
        for course_id in row["subjects"]
    }
    if course_ids:
        _add_virtual_classroom_metrics(rows, course_ids, cutoff)
        _add_grade_metrics(rows, course_ids, start, cutoff)
        _add_topic_metrics(rows, course_ids, cutoff, selected_teacher)

    report_rows = []
    for row in rows.values():
        row["subjects"] = sorted(
            (finalize_metrics(detail) for detail in row["subjects"].values()),
            key=lambda detail: (detail["grupo"].nombre, detail["materia"].nombre),
        )
        row["metrics"] = finalize_metrics(row["metrics"])
        report_rows.append(row)
    report_rows.sort(key=lambda row: ((row["teacher"].apellido or ""), row["teacher"].nombre))
    return {
        "rows": report_rows,
        "summary": summarize(report_rows),
        "start": start,
        "end": end,
        "cutoff": cutoff,
    }


def _active_students_by_group(course_ids, cutoff):
    assignments = GrupoEstudiante.objects.filter(
        grupo__materia_cursos__id__in=course_ids,
        estado="activo",
        estudiante__activo=True,
        fecha_asignacion__lte=cutoff,
    ).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=cutoff)).values_list(
        "grupo_id", "estudiante_id"
    ).distinct()
    result = defaultdict(set)
    for group_id, student_id in assignments:
        result[group_id].add(student_id)
    return result


def _confirmed_students_by_course(course_ids):
    result = defaultdict(set)
    enrollments = MoodleMatricula.objects.filter(
        curso__materia_curso_id__in=course_ids,
        confirmada=True,
        rol="Alumno",
    ).values_list("curso__materia_curso_id", "cuenta__persona_id")
    for course_id, student_id in enrollments:
        result[course_id].add(student_id)
    return result


def _add_virtual_classroom_metrics(rows, course_ids, cutoff):
    group_students = _active_students_by_group(course_ids, cutoff)
    confirmed = _confirmed_students_by_course(course_ids)
    for row in rows.values():
        for detail in row["subjects"].values():
            expected = group_students[detail["grupo"].pk]
            enrolled = expected & confirmed[detail["materia_curso"].pk]
            detail["virtual_expected"] = len(expected)
            detail["virtual_confirmed"] = len(enrolled)
            row["metrics"]["virtual_expected"] += len(expected)
            row["metrics"]["virtual_confirmed"] += len(enrolled)


def _normalized_grade(value, minimum, maximum):
    if value is None or minimum is None or maximum is None or maximum <= minimum:
        return None
    normalized = ((value - minimum) / (maximum - minimum)) * 100
    return float(max(0, min(normalized, 100)))


def _add_grade_metrics(rows, course_ids, start, cutoff):
    grades = MoodleCalificacion.objects.filter(
        matricula__curso__materia_curso_id__in=course_ids,
        matricula__confirmada=True,
        matricula__rol="Alumno",
        activa=True,
        oculta=False,
        tipo="mod",
        nota__isnull=False,
        fecha_calificacion__date__gte=start,
        fecha_calificacion__date__lte=cutoff,
    ).values_list(
        "matricula__curso__materia_curso_id",
        "matricula__cuenta__persona_id",
        "nota",
        "nota_minima",
        "nota_maxima",
    )
    by_course = defaultdict(lambda: defaultdict(list))
    for course_id, student_id, value, minimum, maximum in grades:
        normalized = _normalized_grade(value, minimum, maximum)
        if normalized is not None:
            by_course[course_id][student_id].append(normalized)

    group_students = _active_students_by_group(course_ids, cutoff)
    for row in rows.values():
        for detail in row["subjects"].values():
            course_id = detail["materia_curso"].pk
            expected = group_students[detail["grupo"].pk]
            student_values = [
                sum(values) / len(values)
                for student_id, values in by_course[course_id].items()
                if student_id in expected and values
            ]
            detail["grade_students"] = len(student_values)
            detail["grade_expected_students"] = len(expected)
            detail["grade_activities"] = sum(
                len(values)
                for student_id, values in by_course[course_id].items()
                if student_id in expected
            )
            detail["grade_student_values"].extend(student_values)
            row["metrics"]["grade_students"] += len(student_values)
            row["metrics"]["grade_expected_students"] += len(expected)
            row["metrics"]["grade_activities"] += detail["grade_activities"]
            row["metrics"]["grade_student_values"].extend(student_values)


def _add_topic_metrics(rows, course_ids, cutoff, selected_teacher):
    subtopics = Subtema.objects.filter(
        tema__planificacion__materia_curso_id__in=course_ids
    ).values_list("tema__planificacion__materia_curso_id", "id")
    totals = defaultdict(set)
    for course_id, subtopic_id in subtopics:
        totals[course_id].add(subtopic_id)

    historical = list(
        Clase.objects.filter(
            materia_curso_id__in=course_ids,
            fecha__lte=cutoff,
            estado_planificacion="aprobada",
        )
        .select_related("docente", "materia_curso", "subtema")
        .prefetch_related(
            Prefetch(
                "materia_curso__profesor_materia_cursos",
                queryset=ProfesorMateriaCurso.objects.select_related("partner"),
            ),
            "clase_subtemas",
        )
    )
    covered = defaultdict(set)
    for clase in historical:
        for teacher in class_teachers(clase):
            if teacher.pk in rows and (not selected_teacher or teacher.pk == selected_teacher.pk):
                covered[(teacher.pk, clase.materia_curso_id)].update(class_subtopic_ids(clase))

    for teacher_id, row in rows.items():
        for course_id, detail in row["subjects"].items():
            detail["total_subtopics"].update(totals[course_id])
            detail["covered_subtopics"].update(covered[(teacher_id, course_id)])
            row["metrics"]["total_subtopics"].update(totals[course_id])
            row["metrics"]["covered_subtopics"].update(covered[(teacher_id, course_id)])


def summarize(rows):
    metrics = [row["metrics"] for row in rows]
    scheduled = sum(item["scheduled"] for item in metrics)
    attended = sum(item["attended"] for item in metrics)
    suspended = sum(item["suspended"] for item in metrics)
    virtual_expected = sum(item["virtual_expected"] for item in metrics)
    virtual_confirmed = sum(item["virtual_confirmed"] for item in metrics)
    student_present = sum(item["student_present"] for item in metrics)
    student_late = sum(item["student_late"] for item in metrics)
    student_absent = sum(item["student_absent"] for item in metrics)
    return {
        "teachers": len(rows),
        "scheduled": scheduled,
        "teacher_attendance_percent": percent(attended, scheduled - suspended),
        "virtual_percent": percent(virtual_confirmed, virtual_expected),
        "student_attendance_percent": percent(
            student_present + student_late,
            student_present + student_late + student_absent,
        ),
        "late_plans": sum(item["plan_late"] for item in metrics),
    }


def report_teachers():
    return Partner.objects.filter(es_docente=True, activo=True).order_by("apellido", "nombre")
