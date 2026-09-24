from .models import PagoAuditoria


CUOTA_AMOUNT_AUDIT_FIELDS = (
    "valor_cuota",
    "valor_total_plan",
    "saldo_plan",
    "valor_total_curso",
    "saldo_ficha",
)


def decimal_snapshot(**values):
    return {
        field_name: str(values[field_name])
        for field_name in CUOTA_AMOUNT_AUDIT_FIELDS
    }


def registrar_cambio_valor_cuota(*, request, cuota, plan, ficha, datos_anteriores, datos_nuevos):
    user = request.user if request.user.is_authenticated else None
    changes = {
        field_name: {
            "antes": datos_anteriores[field_name],
            "despues": datos_nuevos[field_name],
        }
        for field_name in CUOTA_AMOUNT_AUDIT_FIELDS
        if datos_anteriores[field_name] != datos_nuevos[field_name]
    }
    meta = request.META
    return PagoAuditoria.objects.create(
        tipo_evento="cuota",
        accion="modificar",
        pago_id=None,
        empresa_id=plan.empresa_id,
        cuota_id=cuota.pk,
        plan_pago_id=plan.pk,
        ficha_inscripcion_id=ficha.pk,
        estudiante_id=ficha.estudiante_id,
        usuario_accion_id=getattr(user, "pk", None),
        usuario_accion_username=user.get_username() if user else "",
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos,
        cambios=changes,
        ip_address=meta.get("REMOTE_ADDR") or None,
        metodo_http=request.method,
        ruta=request.path,
        user_agent=meta.get("HTTP_USER_AGENT", ""),
    )


def registrar_cambio_plan_cuotas(*, request, plan, ficha, datos_anteriores, datos_nuevos):
    """Registra en una sola entrada los cambios hechos al convenio desde la ficha."""
    user = request.user if request.user.is_authenticated else None
    fields = datos_anteriores.keys() | datos_nuevos.keys()
    changes = {
        field_name: {
            "antes": datos_anteriores.get(field_name),
            "despues": datos_nuevos.get(field_name),
        }
        for field_name in fields
        if datos_anteriores.get(field_name) != datos_nuevos.get(field_name)
    }
    if not changes:
        return None
    meta = request.META
    return PagoAuditoria.objects.create(
        tipo_evento="cuota",
        accion="modificar",
        pago_id=None,
        empresa_id=plan.empresa_id,
        cuota_id=None,
        plan_pago_id=plan.pk,
        ficha_inscripcion_id=ficha.pk,
        estudiante_id=ficha.estudiante_id,
        usuario_accion_id=getattr(user, "pk", None),
        usuario_accion_username=user.get_username() if user else "",
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos,
        cambios=changes,
        ip_address=meta.get("REMOTE_ADDR") or None,
        metodo_http=request.method,
        ruta=request.path,
        user_agent=meta.get("HTTP_USER_AGENT", ""),
    )
