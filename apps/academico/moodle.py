"""Cliente REST de Moodle. Las credenciales viajan únicamente en el cuerpo POST."""

import base64
import hashlib
import ipaddress
import json
from cryptography.fernet import Fernet, InvalidToken
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, build_opener

from django.conf import settings
from django.db import OperationalError, ProgrammingError
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


def normalize_moodle_url(value):
    """Normaliza una URL y admite HTTP solo para destinos internos."""
    value = (value or "").strip()
    if not value:
        raise MoodleError("Ingresa la URL de Moodle.")
    if "://" not in value:
        candidate_host = value.split("/", 1)[0].split(":", 1)[0].lower()
        try:
            address = ipaddress.ip_address(candidate_host.strip("[]"))
        except ValueError:
            address = None
        internal = (
            candidate_host == "localhost"
            or "." not in candidate_host
            or bool(address and (address.is_private or address.is_loopback or address.is_link_local))
        )
        value = ("http://" if internal else "https://") + value
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        parsed.port
    except ValueError:
        raise MoodleError("La URL de Moodle no es válida.") from None
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise MoodleError("Usa una URL HTTP o HTTPS válida.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise MoodleError("La URL no debe incluir credenciales, parámetros ni fragmentos.")
    hostname = hostname.lower()
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    internal = (
        hostname == "localhost"
        or hostname.endswith(".localhost")
        or "." not in hostname
        or bool(address and (address.is_private or address.is_loopback or address.is_link_local))
    )
    if parsed.scheme == "http" and not internal:
        raise MoodleError("Usa HTTPS. HTTP solo se permite para localhost, nombres internos o IP privadas.")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, path, "", ""))


def _token_cipher(secret):
    key = hashlib.sha256(("moodle-api-token:" + secret).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


@sensitive_variables("token")
def encrypt_moodle_token(token):
    return _token_cipher(settings.SECRET_KEY).encrypt(token.encode()).decode()


def decrypt_moodle_token(encrypted_token):
    if not encrypted_token:
        return ""
    for secret in [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]:
        try:
            return _token_cipher(secret).decrypt(encrypted_token.encode()).decode()
        except InvalidToken:
            continue
    raise MoodleError("No se pudo descifrar el token de Moodle. Revisa la clave del servidor.")


def _saved_configuration():
    # Durante una migración inicial la tabla todavía puede no existir. En ese
    # caso se conserva la compatibilidad temporal con las variables de entorno.
    from .models import MoodleConfiguracion

    try:
        return MoodleConfiguracion.objects.first()
    except (OperationalError, ProgrammingError):
        return None
    except Exception as exc:
        # SimpleTestCase bloquea explícitamente consultas de base de datos.
        if exc.__class__.__name__ == "DatabaseOperationForbidden":
            return None
        raise


class MoodleClient:
    @sensitive_variables("token")
    def __init__(self, configuration=None, *, base_url=None, token=None, timeout=None):
        configuration = configuration if configuration is not None else _saved_configuration()
        if configuration is not None:
            base_url = configuration.base_url
            token = decrypt_moodle_token(configuration.token_cifrado)
        configured_url = base_url or settings.MOODLE_BASE_URL
        self.base_url = normalize_moodle_url(configured_url) if configured_url else ""
        self.token = token if token is not None else settings.MOODLE_TOKEN
        self.timeout = timeout if timeout is not None else settings.MOODLE_TIMEOUT
        self.opener = build_opener(NoRedirects())

    @sensitive_variables()
    def call(self, function, parameters=None):
        url = urlsplit(self.base_url)
        if not self.token or not url.netloc:
            raise MoodleError("Configura la URL y el token de Moodle.")
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
            messages = {
                401: (
                    "Moodle no aceptó las credenciales. Comprueba que el token esté bien escrito "
                    "y siga activo."
                ),
                403: (
                    "El servidor de Moodle no permitió la conexión. Comprueba que el token sea "
                    "válido y que los servicios web estén habilitados. Si el problema continúa, "
                    "pide al encargado del servidor que permita la conexión desde este sistema."
                ),
                404: (
                    "No encontramos el servicio web en esa dirección. Confirma que la URL sea la "
                    "dirección principal de Moodle."
                ),
            }
            if exc.code >= 500:
                message = "Moodle tiene un problema temporal. Espera unos minutos y vuelve a intentarlo."
            else:
                message = messages.get(
                    exc.code,
                    "Moodle rechazó la conexión. Revisa la dirección y vuelve a intentarlo.",
                )
            raise MoodleError(message) from None
        except TimeoutError:
            raise MoodleError("Moodle tardó demasiado en responder. Espera un momento y vuelve a intentarlo.") from None
        except (URLError, OSError):
            raise MoodleError(
                "No pudimos comunicarnos con Moodle. Comprueba que la dirección abra desde este servidor."
            ) from None
        except (ValueError, UnicodeError):
            raise MoodleError(
                "La dirección respondió, pero no parece ser el servicio web de Moodle. Revisa la URL configurada."
            ) from None
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
