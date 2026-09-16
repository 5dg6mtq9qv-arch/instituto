from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal, InvalidOperation
from html import unescape

from django.db import transaction
from django.utils.html import strip_tags

from .models import MoodleCalificacion, MoodleMatricula
from .moodle import MoodleClient, MoodleError


def decimal_value(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def timestamp_value(value):
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=datetime_timezone.utc)
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def clean_text(value, max_length=None):
    text = unescape(strip_tags(str(value or ""))).strip()
    return text[:max_length] if max_length else text


def grade_defaults(item):
    return {
        "nombre": clean_text(item.get("itemname"), 500) or "Actividad sin nombre",
        "tipo": clean_text(item.get("itemtype"), 30),
        "modulo": clean_text(item.get("itemmodule"), 100),
        "instancia_id": item.get("iteminstance") or None,
        "modulo_curso_id": item.get("cmid") or None,
        "categoria_id": item.get("categoryid") or None,
        "nota": decimal_value(item.get("graderaw")),
        "nota_minima": decimal_value(item.get("grademin")),
        "nota_maxima": decimal_value(item.get("grademax")),
        "nota_formateada": clean_text(item.get("gradeformatted"), 100),
        "rango_formateado": clean_text(item.get("rangeformatted"), 100),
        "porcentaje_formateado": clean_text(item.get("percentageformatted"), 100),
        "retroalimentacion": clean_text(item.get("feedback")),
        "fecha_envio": timestamp_value(item.get("gradedatesubmitted")),
        "fecha_calificacion": timestamp_value(item.get("gradedategraded")),
        "oculta": bool(item.get("gradeishidden") or item.get("gradehiddenbydate")),
        "activa": True,
    }


def sync_student_grades(estudiante, client=None):
    enrollments = list(
        MoodleMatricula.objects.select_related(
            "cuenta__persona",
            "curso__materia_curso__materia",
            "curso__materia_curso__grupo",
        ).filter(
            cuenta__persona=estudiante,
            cuenta__usuario_id__isnull=False,
            curso__curso_id__isnull=False,
            rol="Alumno",
            confirmada=True,
        )
    )
    if not enrollments:
        return {"courses": 0, "items": 0, "activities": 0}
    client = client or MoodleClient()

    item_count = 0
    activity_count = 0
    for enrollment in enrollments:
        if enrollment.curso.sitio and enrollment.curso.sitio.rstrip("/") != client.base_url:
            raise MoodleError("El aula del estudiante está vinculada a otra instancia Moodle.")
        try:
            grade_items = client.user_grade_items(
                enrollment.curso.curso_id,
                enrollment.cuenta.usuario_id,
            )
        except MoodleError as exc:
            subject = enrollment.curso.materia_curso.materia.nombre
            raise MoodleError(f"No se pudieron consultar las calificaciones de {subject}. {exc}") from None

        received_ids = set()
        with transaction.atomic():
            for item in grade_items:
                item_id = item["id"]
                received_ids.add(item_id)
                defaults = grade_defaults(item)
                MoodleCalificacion.objects.update_or_create(
                    matricula=enrollment,
                    item_id=item_id,
                    defaults=defaults,
                )
                item_count += 1
                if defaults["tipo"] == "mod":
                    activity_count += 1
            enrollment.calificaciones.exclude(item_id__in=received_ids).update(activa=False)

    return {
        "courses": len(enrollments),
        "items": item_count,
        "activities": activity_count,
    }
