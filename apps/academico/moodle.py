"""Cliente REST de Moodle. Las credenciales viajan únicamente en el cuerpo POST."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

from django.conf import settings
from django.views.decorators.debug import sensitive_variables


REQUIRED_FUNCTIONS = frozenset({
    "core_webservice_get_site_info", "core_course_get_categories",
    "core_course_get_courses_by_field", "core_course_create_courses",
    "core_course_get_contents", "core_user_get_users_by_field",
    "core_user_create_users", "enrol_manual_enrol_users",
    "core_enrol_get_enrolled_users",
    "core_courseformat_update_course", "core_courseformat_get_state",
    "core_courseformat_new_module", "core_update_inplace_editable",
})


def flatten_parameters(parameters):
    """Codifica listas y objetos con los nombres de campos que espera Moodle REST."""
    result = {}

    def visit(key, value):
        if isinstance(value, dict):
            for child, item in value.items():
                visit(f"{key}[{child}]", item)
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                visit(f"{key}[{index}]", item)
        elif value is not None:
            result[key] = int(value) if isinstance(value, bool) else value

    for key, value in parameters.items():
        visit(key, value)
    return result


class MoodleError(Exception):
    """Error seguro para mostrar sin exponer credenciales o respuestas remotas."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class MoodleClient:
    def __init__(self):
        self.base_url = settings.MOODLE_BASE_URL.rstrip("/")
        self.token = settings.MOODLE_TOKEN
        self.timeout = settings.MOODLE_TIMEOUT
        self.opener = build_opener(NoRedirects())

    @sensitive_variables()
    def call(self, function, parameters=None):
        url = urlsplit(self.base_url)
        if not self.token or not url.netloc:
            raise MoodleError("Configura MOODLE_BASE_URL y MOODLE_TOKEN en .env.")
        if url.scheme != "https" or url.username or url.password or url.query or url.fragment:
            raise MoodleError("MOODLE_BASE_URL debe ser una URL HTTPS sin credenciales ni parámetros.")
        payload = flatten_parameters(parameters or {})
        payload.update(wstoken=self.token, wsfunction=function, moodlewsrestformat="json")
        try:
            with self.opener.open(
                self.base_url + "/webservice/rest/server.php",
                data=urlencode(payload).encode("utf-8"),
                timeout=self.timeout,
            ) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise MoodleError(f"Moodle respondió con HTTP {exc.code}. Revisa la URL y el servidor.") from None
        except (URLError, TimeoutError, OSError):
            raise MoodleError("No se pudo conectar con Moodle. Revisa la red y el certificado HTTPS.") from None
        except (ValueError, UnicodeError):
            raise MoodleError("Moodle no devolvió una respuesta JSON válida.") from None
        if isinstance(result, dict) and ("exception" in result or "errorcode" in result):
            messages = {
                "invalidtoken": "El token de Moodle no es válido o ha caducado.",
                "accessexception": "Moodle denegó el acceso. Revisa las funciones y los usuarios autorizados del servicio.",
                "webservice_access_exception": "Moodle denegó el acceso. Revisa los permisos del servicio.",
            }
            raise MoodleError(messages.get(result.get("errorcode"), "Moodle rechazó la operación. Revisa su configuración de servicios web."))
        return result

    def site_info(self):
        result = self.call("core_webservice_get_site_info")
        if not isinstance(result, dict) or not isinstance(result.get("functions"), list):
            raise MoodleError("La información del sitio Moodle tiene un formato inesperado.")
        return result

    def categories(self):
        result = self.call("core_course_get_categories")
        if not isinstance(result, list) or any(
            not isinstance(item, dict) or "id" not in item or "name" not in item for item in result
        ):
            raise MoodleError("La lista de categorías de Moodle tiene un formato inesperado.")
        return result

    def missing_functions(self, info):
        available = {item.get("name") for item in info["functions"] if isinstance(item, dict)}
        return sorted(REQUIRED_FUNCTIONS - available)

    def users_by_field(self, field, values):
        if field not in {"id", "idnumber", "username", "email"}:
            raise MoodleError("Campo de búsqueda de usuarios no permitido.")
        return self._records("core_user_get_users_by_field", {"field": field, "values": list(values)})

    def create_users(self, users):
        return self._records("core_user_create_users", {"users": users})

    def enrol_users(self, enrolments):
        result = self.call("enrol_manual_enrol_users", {"enrolments": enrolments})
        if result is not None:
            raise MoodleError("Moodle devolvió una respuesta inesperada al matricular usuarios.")

    def enrolled_users(self, course_id):
        return self._records("core_enrol_get_enrolled_users", {"courseid": course_id})

    def course_state(self, course_id):
        result = self.call("core_courseformat_get_state", {"courseid": course_id})
        try:
            state = json.loads(result)
        except (TypeError, ValueError):
            raise MoodleError("Moodle devolvió una estructura de curso inesperada.") from None
        if not isinstance(state, dict) or not isinstance(state.get("section"), list) or not isinstance(state.get("cm"), list):
            raise MoodleError("Moodle devolvió una estructura de curso incompleta.")
        return state

    def add_section(self, course_id):
        result = self.call("core_courseformat_update_course", {
            "action": "section_add", "courseid": course_id, "ids": [],
        })
        try:
            json.loads(result)
        except (TypeError, ValueError):
            raise MoodleError("Moodle no confirmó la creación de una sección.") from None

    def rename_section(self, section_id, name):
        result = self.call("core_update_inplace_editable", {
            "component": "format_topics", "itemtype": "sectionname",
            "itemid": section_id, "value": name,
        })
        if not isinstance(result, dict):
            raise MoodleError("Moodle no confirmó el nombre de una sección.")

    def create_subsection(self, course_id, section_id):
        result = self.call("core_courseformat_new_module", {
            "courseid": course_id, "modname": "subsection", "targetsectionid": section_id,
        })
        try:
            updates = json.loads(result)
        except (TypeError, ValueError):
            raise MoodleError("Moodle creó una subsección, pero no confirmó su identificador. Reintenta la sincronización.") from None
        candidates = [
            item.get("fields", {}) for item in updates
            if item.get("name") == "cm" and item.get("action") == "put"
            and item.get("fields", {}).get("module") == "subsection"
            and str(item.get("fields", {}).get("sectionid")) == str(section_id)
        ] if isinstance(updates, list) else []
        if not candidates:
            raise MoodleError("Moodle creó una subsección, pero no confirmó su identificador. Reintenta la sincronización.")
        return max(candidates, key=lambda item: int(item["id"]))

    def rename_activity(self, activity_id, name):
        result = self.call("core_update_inplace_editable", {
            "component": "core_course", "itemtype": "activityname",
            "itemid": activity_id, "value": name,
        })
        if not isinstance(result, dict):
            raise MoodleError("Moodle no confirmó el nombre de una subsección.")

    def _records(self, function, parameters):
        result = self.call(function, parameters)
        if not isinstance(result, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("id"), int) for item in result
        ):
            raise MoodleError("Moodle devolvió una lista de usuarios con formato inesperado.")
        return result
