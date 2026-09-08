"""Identidad estable y credenciales iniciales de Moodle."""
import base64
import hashlib
import re

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import connection, transaction
from django.utils.text import slugify
from django.views.decorators.debug import sensitive_variables

from .models import MoodleCuenta
from .moodle import MoodleError


def cipher(secret=None):
    key = hashlib.sha256(("moodle-initial-password:" + (secret or settings.SECRET_KEY)).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def initial_password(account):
    if not account.clave_inicial_cifrada:
        return ""
    for secret in [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]:
        try:
            return cipher(secret).decrypt(account.clave_inicial_cifrada.encode()).decode()
        except InvalidToken:
            continue
    raise MoodleError("No se pudo descifrar la clave inicial. Revisa la clave de cifrado del servidor.")


def person_names(person):
    names = person.nombre.strip().split()
    surname = (person.apellido or "").strip()
    if surname:
        return " ".join(names), surname
    if len(names) > 1:
        return " ".join(names[:-1]), names[-1]
    return names[0], "docente" if person.es_docente else "alumno"


def username_base(person):
    first, last = person_names(person)
    first = slugify(first.split()[0]).replace("-", "") or "usuario"
    last = slugify(last.split()[0]).replace("-", "") or "alumno"
    return f"{first}_{last}"[:60]


def legacy_teacher_username(person, username):
    """Detecta únicamente el respaldo antiguo nombre_alumno[1..n] en docentes sin apellido."""
    if not person.es_docente or (person.apellido or "").strip():
        return False
    names = (person.nombre or "").strip().split()
    if len(names) != 1:
        return False
    first = slugify(names[0]).replace("-", "") or "usuario"
    return bool(re.fullmatch(rf"{re.escape(first)}_alumno\d*", username))


def available_username(client, person, *, current_account=None):
    base = username_base(person)
    for suffix in range(10000):
        username = base + (str(suffix) if suffix else "")
        local_accounts = MoodleCuenta.objects.filter(sitio=client.base_url, usuario=username)
        if current_account:
            local_accounts = local_accounts.exclude(pk=current_account.pk)
        if local_accounts.exists():
            continue
        remote_users = client.users_by_field("username", [username])
        if remote_users and not (
            current_account
            and current_account.usuario_id
            and len(remote_users) == 1
            and remote_users[0].get("id") == current_account.usuario_id
        ):
            continue
        if not (person.email or "").strip() and client.users_by_field(
            "email", [account_email(person, username)]
        ):
            continue
        return username
    raise MoodleError("No se encontró un nombre de usuario disponible.")


def account_email(person, username):
    return (person.email or "").strip().lower() or f"{username}@{settings.MOODLE_FALLBACK_EMAIL_DOMAIN}"


def active_user(users, person):
    if len(users) != 1 or not users[0].get("username"):
        raise MoodleError(f"No se pudo identificar de forma única la cuenta Moodle de {person}.")
    user = users[0]
    if user.get("suspended") or user.get("deleted"):
        raise MoodleError(f"La cuenta Moodle de {person} está suspendida o eliminada.")
    return user


@sensitive_variables()
def ensure_account(client, person):
    # Compartido por todas las materias: evita reservar el mismo usuario en dos
    # cursos simultáneos. La reserva se conserva al capturar errores de Moodle.
    error = None
    account = None
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [72419603])
        try:
            account = _ensure_account(client, person)
        except MoodleError as exc:
            error = exc
    if error:
        raise error
    return account


@sensitive_variables()
def _ensure_account(client, person):
    account = MoodleCuenta.objects.filter(persona=person, sitio=client.base_url).first()
    if account and account.usuario_id:
        user = active_user(client.users_by_field("id", [account.usuario_id]), person)
        if legacy_teacher_username(person, user["username"]):
            previous_username = user["username"]
            new_username = available_username(client, person, current_account=account)
            update = {"id": account.usuario_id, "username": new_username}
            provisional_email = f"{previous_username}@{settings.MOODLE_FALLBACK_EMAIL_DOMAIN}".lower()
            if not (person.email or "").strip() and (user.get("email") or "").lower() == provisional_email:
                update["email"] = account_email(person, new_username)
            client.update_users([update])
            user = active_user(client.users_by_field("id", [account.usuario_id]), person)
            if user["username"] != new_username:
                raise MoodleError(
                    "Moodle no confirmó el nuevo usuario del docente. Se volverá a intentar.",
                    retryable=True,
                )
        if user["username"] != account.usuario:
            account.usuario = user["username"]
            account.save(update_fields=["usuario"])
        return account
    if not account:
        email = (person.email or "").strip().lower()
        existing = client.users_by_field("email", [email]) if email else []
        if existing:
            user = active_user(existing, person)
            if MoodleCuenta.objects.filter(sitio=client.base_url, usuario_id=user["id"]).exclude(persona=person).exists():
                raise MoodleError("La cuenta Moodle ya está vinculada a otra persona del instituto.")
            return MoodleCuenta.objects.create(persona=person, sitio=client.base_url,
                                              usuario=user["username"], usuario_id=user["id"])
        if not settings.MOODLE_INITIAL_PASSWORD:
            raise MoodleError("Configura MOODLE_INITIAL_PASSWORD antes de crear cuentas nuevas.")
        username = available_username(client, person)
        account = MoodleCuenta.objects.create(
            persona=person, sitio=client.base_url, usuario=username,
            clave_inicial_cifrada=cipher().encrypt(settings.MOODLE_INITIAL_PASSWORD.encode()).decode(),
        )
    marker = "instituto-" + str(account.clave)
    existing = client.users_by_field("username", [account.usuario])
    if existing:
        user = active_user(existing, person)
        if user.get("idnumber") != marker:
            raise MoodleError("El usuario reservado pertenece a otra cuenta Moodle. Revisa la vinculación.")
    else:
        first, last = person_names(person)
        created = client.create_users([{
            "username": account.usuario, "idnumber": marker,
            "firstname": first, "lastname": last, "email": account_email(person, account.usuario),
            "auth": "manual", "password": initial_password(account), "createpassword": False,
            "preferences": [{"type": "auth_forcepasswordchange", "value": "1"}],
        }])
        user = active_user(created, person)
    account.usuario_id = user["id"]
    account.save(update_fields=["usuario_id"])
    return account
