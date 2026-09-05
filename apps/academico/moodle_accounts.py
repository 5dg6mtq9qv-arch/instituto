"""Identidad estable y credenciales iniciales de Moodle."""
import base64
import hashlib

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
    return names[0], "alumno"


def username_base(person):
    first, last = person_names(person)
    first = slugify(first.split()[0]).replace("-", "") or "usuario"
    last = slugify(last.split()[0]).replace("-", "") or "alumno"
    return f"{first}_{last}"[:60]


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
        base = username_base(person)
        for suffix in range(10000):
            username = base + (str(suffix) if suffix else "")
            if MoodleCuenta.objects.filter(sitio=client.base_url, usuario=username).exists():
                continue
            if client.users_by_field("username", [username]):
                continue
            if not email and client.users_by_field("email", [account_email(person, username)]):
                continue
            account = MoodleCuenta.objects.create(
                persona=person, sitio=client.base_url, usuario=username,
                clave_inicial_cifrada=cipher().encrypt(settings.MOODLE_INITIAL_PASSWORD.encode()).decode(),
            )
            break
        else:
            raise MoodleError("No se encontró un nombre de usuario disponible.")
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
