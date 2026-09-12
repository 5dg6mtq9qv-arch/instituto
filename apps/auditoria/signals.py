from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.cartera.models import Cuota, Pago
from apps.core.current_user import get_current_request

from .models import PagoAuditoria


AUDITED_FIELDS = (
    "empresa_id",
    "cuota_id",
    "forma_pago_id",
    "fecha_registro",
    "valor",
    "numero_documento",
    "comprobante",
    "comentario",
    "usuario_id",
    "usuario_updated_id",
)


def serialize_value(value):
    if hasattr(value, "name"):
        return value.name or ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def pago_snapshot(pago):
    return {
        field_name: serialize_value(getattr(pago, field_name, None))
        for field_name in AUDITED_FIELDS
    }


def payment_context(pago):
    if not pago.cuota_id:
        return {}
    return (
        Cuota.objects.filter(pk=pago.cuota_id)
        .values(
            "plan_pago_id",
            "plan_pago__ficha_inscripcion_id",
            "plan_pago__ficha_inscripcion__estudiante_id",
        )
        .first()
        or {}
    )


def request_metadata(pago):
    request = get_current_request()
    request_user = getattr(request, "user", None)
    if not request_user or not request_user.is_authenticated:
        request_user = None
    actor = request_user or pago.usuario_updated or pago.usuario
    meta = getattr(request, "META", {}) if request else {}
    return {
        "usuario_accion_id": getattr(actor, "pk", None),
        "usuario_accion_username": actor.get_username() if actor else "",
        "ip_address": meta.get("REMOTE_ADDR") or None,
        "metodo_http": getattr(request, "method", "") if request else "",
        "ruta": getattr(request, "path", "") if request else "",
        "user_agent": meta.get("HTTP_USER_AGENT", ""),
    }


@receiver(pre_save, sender=Pago)
def capture_previous_payment(sender, instance, using, raw=False, **kwargs):
    if raw or not instance.pk:
        instance._audit_previous_snapshot = None
        return
    previous = sender.objects.using(using).filter(pk=instance.pk).first()
    instance._audit_previous_snapshot = pago_snapshot(previous) if previous else None


@receiver(post_save, sender=Pago)
def audit_payment_save(sender, instance, created, raw=False, using=None, **kwargs):
    if raw:
        return

    previous = getattr(instance, "_audit_previous_snapshot", None)
    current = pago_snapshot(instance)
    changes = {}
    if previous is not None:
        changes = {
            field_name: {"antes": previous.get(field_name), "despues": current.get(field_name)}
            for field_name in AUDITED_FIELDS
            if previous.get(field_name) != current.get(field_name)
        }
    if not created and not changes:
        return

    context = payment_context(instance)
    PagoAuditoria.objects.using(using).create(
        accion="crear" if created else "modificar",
        pago_id=instance.pk,
        empresa_id=instance.empresa_id,
        cuota_id=instance.cuota_id,
        plan_pago_id=context.get("plan_pago_id"),
        ficha_inscripcion_id=context.get("plan_pago__ficha_inscripcion_id"),
        estudiante_id=context.get("plan_pago__ficha_inscripcion__estudiante_id"),
        forma_pago_id=instance.forma_pago_id,
        usuario_pago_id=instance.usuario_id,
        datos_anteriores=previous or {},
        datos_nuevos=current,
        cambios=changes,
        **request_metadata(instance),
    )
