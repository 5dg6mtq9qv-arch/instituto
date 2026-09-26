"""Sincronizacion del estado de usuarios locales con Moodle."""

from .models import MoodleCuenta
from .moodle import MoodleClient


DEFAULT_BATCH_SIZE = 100


def inactive_student_accounts(client):
    """Devuelve cuentas Moodle confirmadas de estudiantes inactivos."""
    return list(
        MoodleCuenta.objects.filter(
            sitio=client.base_url,
            usuario_id__isnull=False,
            persona__es_estudiante=True,
            persona__activo=False,
        )
        .select_related("persona")
        .order_by("pk")
    )


def suspend_inactive_students(*, client=None, apply=False, batch_size=DEFAULT_BATCH_SIZE):
    """Suspende en Moodle las cuentas vinculadas a estudiantes inactivos.

    La operacion es idempotente: Moodle acepta volver a guardar ``suspended=1``.
    Con ``apply=False`` solo devuelve las cuentas que serian procesadas.
    """
    client = client or MoodleClient()
    accounts = inactive_student_accounts(client)

    if apply:
        for start in range(0, len(accounts), batch_size):
            batch = accounts[start : start + batch_size]
            client.update_users(
                [{"id": account.usuario_id, "suspended": 1} for account in batch]
            )

    return accounts
