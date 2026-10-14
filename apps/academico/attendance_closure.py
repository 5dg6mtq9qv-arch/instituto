from django.utils import timezone

from .models import Clase


def close_overdue_attendances(now=None):
    """Close classes through the current day without changing attendance records."""
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    return Clase.objects.filter(fecha__lte=today, asistencia_cerrada=False).update(
        asistencia_cerrada=True,
        asistencia_cierre_automatico=True,
        asistencia_cerrada_por=None,
        fecha_cierre_asistencia=now,
    )
