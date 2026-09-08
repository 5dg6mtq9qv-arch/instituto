"""Creación reintentable de aulas; no elimina cursos ni participantes de Moodle."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils.html import escape

from .models import GrupoEstudiante, MoodleCuenta, MoodleCurso, MoodleMatricula, Tema
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
        raise MoodleError("Moodle no creó todas las secciones del temario.", retryable=True)

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
        raise MoodleError(
            "El curso existe, pero faltan subsecciones. Reintenta la sincronización.",
            retryable=True,
        )


MOODLE_SYNC_STEPS = (
    ("connection", "Conexión y permisos"),
    ("course", "Creación o recuperación del aula"),
    ("structure", "Temas y subtemas"),
    ("accounts", "Cuentas de participantes"),
    ("enrolments", "Matrículas y comprobación final"),
)


def participant_roles(data):
    roles = {
        person.pk: (person, settings.MOODLE_STUDENT_ROLE_ID)
        for person in data["alumnos"]
    }
    roles.update({
        person.pk: (person, settings.MOODLE_TEACHER_ROLE_ID)
        for person in data["docentes"]
    })
    return roles


def participants_are_confirmed(link, roles):
    confirmed = set(
        link.matriculas.filter(confirmada=True).values_list("cuenta__persona_id", flat=True)
    )
    return link.completo and set(roles).issubset(confirmed)


def ensure_remote_course(client, link, materia_curso, data):
    if link.curso_id:
        return f"Aula recuperada con el identificador Moodle {link.curso_id}."

    key = "instituto-" + str(link.clave)
    result = client.call("core_course_get_courses_by_field", {"field": "shortname", "value": key})
    if not isinstance(result, dict) or not isinstance(result.get("courses"), list):
        raise MoodleError("Moodle no pudo confirmar si el curso ya existe.", retryable=True)
    courses = result["courses"]
    recovered = bool(courses)
    if not courses:
        courses = client.call("core_course_create_courses", {"courses": [{
            "fullname": f"{materia_curso.materia} – {materia_curso.grupo}",
            "shortname": key,
            "idnumber": key,
            "categoryid": settings.MOODLE_CATEGORY_ID,
            "format": "topics",
            "summary": temario_summary(data["temas"]),
            "summaryformat": 1,
            "courseformatoptions": [{"name": "numsections", "value": len(data["temas"])}],
        }]})
    if (
        not isinstance(courses, list)
        or len(courses) != 1
        or not isinstance(courses[0], dict)
        or not isinstance(courses[0].get("id"), int)
    ):
        raise MoodleError(
            "Moodle no confirmó el curso. Reintenta para recuperar su estado.",
            retryable=True,
        )
    link.curso_id = courses[0]["id"]
    link.save(update_fields=["curso_id"])
    action = "recuperada" if recovered else "creada"
    return f"Aula {action} y confirmada por Moodle con ID {link.curso_id}."


def sync_participant_accounts(client, link, data):
    roles = participant_roles(data)
    if participants_are_confirmed(link, roles):
        return f"Las {len(roles)} cuentas ya estaban vinculadas y confirmadas."

    link.completo = False
    link.save(update_fields=["completo"])
    reused = 0
    created_or_linked = 0
    for person, role in roles.values():
        had_account = MoodleCuenta.objects.filter(persona=person, sitio=client.base_url).exists()
        account = ensure_account(client, person)
        MoodleMatricula.objects.update_or_create(
            curso=link,
            cuenta=account,
            defaults={"rol": "Docente" if role == settings.MOODLE_TEACHER_ROLE_ID else "Alumno"},
        )
        if had_account:
            reused += 1
        else:
            created_or_linked += 1
    return (
        f"{len(roles)} cuenta(s) confirmada(s): {reused} reutilizada(s) y "
        f"{created_or_linked} creada(s) o vinculada(s)."
    )


def sync_enrolments(client, link, data):
    roles = participant_roles(data)
    if participants_are_confirmed(link, roles):
        return f"Las {len(roles)} matrículas ya estaban confirmadas en Moodle."

    enrolments = []
    for person, role in roles.values():
        account = MoodleCuenta.objects.filter(
            persona=person,
            sitio=client.base_url,
            usuario_id__isnull=False,
        ).first()
        if not account:
            raise MoodleError(
                f"La cuenta Moodle de {person} aún no está confirmada. Se repetirá la etapa de cuentas.",
                retryable=True,
            )
        MoodleMatricula.objects.update_or_create(
            curso=link,
            cuenta=account,
            defaults={"rol": "Docente" if role == settings.MOODLE_TEACHER_ROLE_ID else "Alumno"},
        )
        enrolments.append({"roleid": role, "userid": account.usuario_id, "courseid": link.curso_id})

    client.enrol_users(enrolments)
    enrolled = {user["id"] for user in client.enrolled_users(link.curso_id)}
    expected = {enrolment["userid"] for enrolment in enrolments}
    if not expected.issubset(enrolled):
        raise MoodleError(
            "El curso existe, pero faltan participantes. Reintenta la matrícula.",
            retryable=True,
        )
    link.matriculas.filter(cuenta__usuario_id__in=enrolled).update(confirmada=True)
    link.completo = True
    link.save(update_fields=["completo"])
    return f"{len(expected)} participante(s) matriculado(s) y comprobado(s) en Moodle."


def sync_moodle_course_step(materia_curso, step):
    """Ejecuta y confirma una fase real; cada fase puede repetirse sin duplicar datos."""
    step_names = {name for name, _label in MOODLE_SYNC_STEPS}
    if step not in step_names:
        raise MoodleError("La etapa de sincronización solicitada no es válida.")

    # La clave se guarda antes del acceso remoto para recuperar creaciones cuya
    # respuesta se haya perdido por un corte de red.
    link, _created = MoodleCurso.objects.get_or_create(materia_curso=materia_curso)
    error = None
    detail = ""
    with transaction.atomic():
        link = MoodleCurso.objects.select_for_update().get(pk=link.pk)
        try:
            client = MoodleClient()
            if link.sitio and link.sitio != client.base_url:
                raise MoodleError("El aula está vinculada a otra instancia Moodle.")
            data = course_data(materia_curso)
            if data["errors"]:
                raise MoodleError(" ".join(data["errors"]))

            if step == "connection":
                missing = client.missing_functions(client.site_info())
                if missing:
                    raise MoodleError("Faltan funciones Moodle: " + ", ".join(missing))
                link.sitio = client.base_url
                link.save(update_fields=["sitio"])
                detail = (
                    f"Conexión confirmada. Se procesarán {len(data['temas'])} tema(s), "
                    f"{len(data['docentes'])} docente(s) y {len(data['alumnos'])} alumno(s)."
                )
            else:
                if not link.sitio:
                    link.sitio = client.base_url
                    link.save(update_fields=["sitio"])
                if step == "course":
                    detail = ensure_remote_course(client, link, materia_curso, data)
                elif not link.curso_id:
                    raise MoodleError(
                        "El aula todavía no está confirmada. Se repetirá la etapa de creación.",
                        retryable=True,
                    )
                elif step == "structure":
                    sync_course_structure(client, link.curso_id, data["temas"])
                    subtopics = sum(len(topic.subtemas_planificacion.all()) for topic in data["temas"])
                    detail = (
                        f"Moodle confirmó {len(data['temas'])} tema(s) y {subtopics} subtema(s)."
                    )
                elif step == "accounts":
                    detail = sync_participant_accounts(client, link, data)
                elif step == "enrolments":
                    detail = sync_enrolments(client, link, data)
        except MoodleError as exc:
            # Los identificadores y reservas logrados antes del corte se confirman
            # al salir de la transacción y serán reutilizados por el reintento.
            error = exc
    if error:
        raise error
    return {"link": link, "step": step, "detail": detail}


def create_moodle_course(materia_curso):
    result = None
    for step, _label in MOODLE_SYNC_STEPS:
        result = sync_moodle_course_step(materia_curso, step)
    return result["link"]
