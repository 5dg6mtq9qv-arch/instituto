"""Creación reintentable de aulas; no elimina cursos ni participantes de Moodle."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils.html import escape

from .models import GrupoEstudiante, MoodleCurso, MoodleMatricula, Tema
from .moodle_accounts import ensure_account
from .moodle import MoodleClient, MoodleError


def course_data(materia_curso):
    temas = list(Tema.objects.filter(planificacion__materia_curso=materia_curso)
                 .prefetch_related("subtemas_planificacion").order_by("orden", "pk"))
    docentes = [a.partner for a in materia_curso.profesor_materia_cursos.filter(
        auto_generada_por_clases=False, partner__activo=True).select_related("partner")]
    alumnos = list({a.estudiante_id: a.estudiante for a in GrupoEstudiante.objects.filter(
        grupo=materia_curso.grupo, estado="activo", estudiante__activo=True
    ).select_related("estudiante")}.values())
    errors = []
    if not temas:
        errors.append("La materia no tiene temas en su planificación.")
    if not docentes:
        errors.append("La materia no tiene docente activo asignado.")
    if not alumnos:
        errors.append("El grupo no tiene alumnos activos matriculados.")
    emails = {}
    for person in docentes + alumnos:
        email = (person.email or "").strip().lower()
        if email:
            try:
                validate_email(email)
            except ValidationError:
                errors.append(f"{person}: el correo registrado no es válido.")
            if email in emails and emails[email] != person.pk:
                errors.append(f"El correo de {person} está compartido con otra persona.")
            emails[email] = person.pk
        if not (person.nombre or "").strip():
            errors.append("Hay un participante sin nombre.")
    return {"temas": temas, "docentes": docentes, "alumnos": alumnos, "errors": errors}


def temario_summary(temas):
    parts = ["<h2>Temario</h2><ol>"]
    for tema in temas:
        parts.append(f"<li><strong>{escape(tema.nombre)}</strong>")
        if tema.detalle:
            parts.append(f"<p>{escape(tema.detalle)}</p>")
        parts.append("<ul>")
        for subtema in sorted(tema.subtemas_planificacion.all(), key=lambda item: (item.orden, item.pk)):
            parts.append(f"<li>{escape(subtema.nombre)}</li>")
        parts.append("</ul></li>")
    return "".join(parts) + "</ol>"


def section_name(index, tema):
    prefix = f"Tema {index}:"
    return tema.nombre if tema.nombre.lower().startswith(prefix.lower()) else f"{prefix} {tema.nombre}"


def subsection_name(topic_index, subtopic_index, subtema):
    return f"Subtema {topic_index}.{subtopic_index}: {subtema.nombre}"


def sync_course_structure(client, course_id, temas):
    """Crea las secciones principales y las subsecciones reales de Moodle 5.1."""
    state = client.course_state(course_id)
    sections = sorted(
        (item for item in state["section"] if item.get("section", 0) > 0 and not item.get("component")),
        key=lambda item: item["section"],
    )
    for _ in range(len(temas) - len(sections)):
        client.add_section(course_id)
    state = client.course_state(course_id)
    sections = sorted(
        (item for item in state["section"] if item.get("section", 0) > 0 and not item.get("component")),
        key=lambda item: item["section"],
    )
    if len(sections) < len(temas):
        raise MoodleError("Moodle no creó todas las secciones del temario.")

    for index, (tema, section) in enumerate(zip(temas, sections), start=1):
        expected = section_name(index, tema)
        if section.get("rawtitle") != expected:
            client.rename_section(section["id"], expected)

    for topic_index, (tema, section) in enumerate(zip(temas, sections), start=1):
        subtemas = sorted(tema.subtemas_planificacion.all(), key=lambda item: (item.orden, item.pk))
        state = client.course_state(course_id)
        cms = {str(item["id"]): item for item in state["cm"] if item.get("id") is not None}
        existing = [cms[str(cmid)] for cmid in section.get("cmlist", []) if str(cmid) in cms and cms[str(cmid)].get("module") == "subsection"]
        expected_names = [subsection_name(topic_index, index, subtema) for index, subtema in enumerate(subtemas, start=1)]
        named = {item.get("name"): item for item in existing}
        unused = [item for item in existing if item.get("name") not in expected_names]
        for expected in expected_names:
            if expected in named:
                continue
            subsection = unused.pop(0) if unused else client.create_subsection(course_id, section["id"])
            client.rename_activity(subsection["id"], expected)

    final_state = client.course_state(course_id)
    final_cms = {item.get("name") for item in final_state["cm"] if item.get("module") == "subsection"}
    expected = {
        subsection_name(topic_index, subtopic_index, subtema)
        for topic_index, tema in enumerate(temas, start=1)
        for subtopic_index, subtema in enumerate(
            sorted(tema.subtemas_planificacion.all(), key=lambda item: (item.orden, item.pk)), start=1
        )
    }
    if not expected.issubset(final_cms):
        raise MoodleError("El curso existe, pero faltan subsecciones. Reintenta la sincronización.")


def create_moodle_course(materia_curso):
    # Persistir la clave antes del primer acceso remoto permite recuperar un curso
    # incluso cuando Moodle lo crea y se interrumpe su respuesta.
    link, _ = MoodleCurso.objects.get_or_create(materia_curso=materia_curso)
    error = None
    with transaction.atomic():
        link = MoodleCurso.objects.select_for_update().get(pk=link.pk)
        client = MoodleClient()
        if link.sitio and link.sitio != client.base_url:
            raise MoodleError("El aula está vinculada a otra instancia Moodle.")
        data = course_data(materia_curso)
        if data["errors"]:
            raise MoodleError(" ".join(data["errors"]))
        try:
            missing = client.missing_functions(client.site_info())
            if missing:
                raise MoodleError("Faltan funciones Moodle: " + ", ".join(missing))
            link.sitio = client.base_url
            link.save(update_fields=["sitio"])
            key = "instituto-" + str(link.clave)
            if not link.curso_id:
                result = client.call("core_course_get_courses_by_field", {"field": "shortname", "value": key})
                if not isinstance(result, dict) or not isinstance(result.get("courses"), list):
                    raise MoodleError("Moodle no pudo confirmar si el curso ya existe.")
                courses = result["courses"]
                if not courses:
                    courses = client.call("core_course_create_courses", {"courses": [{
                        "fullname": f"{materia_curso.materia} – {materia_curso.grupo}",
                        "shortname": key, "idnumber": key,
                        "categoryid": settings.MOODLE_CATEGORY_ID,
                        "format": "topics", "summary": temario_summary(data["temas"]),
                        "summaryformat": 1,
                        "courseformatoptions": [{"name": "numsections", "value": len(data["temas"])}],
                    }]})
                if not isinstance(courses, list) or len(courses) != 1 or not isinstance(courses[0], dict) or not isinstance(courses[0].get("id"), int):
                    raise MoodleError("Moodle no confirmó el curso. Reintenta para recuperar su estado.")
                link.curso_id = courses[0]["id"]
            link.sitio = client.base_url
            link.save(update_fields=["sitio", "curso_id"])
            sync_course_structure(client, link.curso_id, data["temas"])
            if link.completo:
                return link
            roles = {}
            for person in data["alumnos"]:
                roles[person.pk] = (person, settings.MOODLE_STUDENT_ROLE_ID)
            for person in data["docentes"]:
                roles[person.pk] = (person, settings.MOODLE_TEACHER_ROLE_ID)
            enrolments = []
            for person, role in roles.values():
                account = ensure_account(client, person)
                MoodleMatricula.objects.update_or_create(
                    curso=link, cuenta=account,
                    defaults={"rol": "Docente" if role == settings.MOODLE_TEACHER_ROLE_ID else "Alumno"},
                )
                enrolments.append({"roleid": role, "userid": account.usuario_id, "courseid": link.curso_id})
            client.enrol_users(enrolments)
            enrolled = {u["id"] for u in client.enrolled_users(link.curso_id)}
            if not {e["userid"] for e in enrolments}.issubset(enrolled):
                raise MoodleError("El curso existe, pero faltan participantes. Reintenta la matrícula.")
            link.matriculas.filter(cuenta__usuario_id__in=enrolled).update(confirmada=True)
            link.completo = True
            link.save(update_fields=["completo"])
        except MoodleError as exc:
            # Conservar el identificador si una matrícula falla después de crear el curso.
            error = exc
    if error:
        raise error
    return link
