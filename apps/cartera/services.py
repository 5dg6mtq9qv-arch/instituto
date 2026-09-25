from decimal import Decimal

from django.utils import timezone

from apps.matricula.models import FichaInscripcion

from .models import Cuota, Pago, PlanPago


def sync_ficha_payment_summary(ficha, plan, user):
    proxima_cuota = next(
        (
            cuota
            for cuota in plan.cuotas.filter(activo=True)
            .exclude(estado="anulada")
            .order_by("fecha_pago_debito", "numero")
            if cuota.saldo() > 0
        ),
        None,
    )
    ficha.abono = plan.abono
    ficha.saldo = plan.saldo
    ficha.fecha_proximo_pago = proxima_cuota.fecha_pago_debito if proxima_cuota else None
    ficha.valor_proximo_pago = proxima_cuota.saldo() if proxima_cuota else Decimal("0.00")
    ficha.usuario_updated = user
    ficha.save(
        update_fields=[
            "abono", "saldo", "fecha_proximo_pago", "valor_proximo_pago",
            "usuario_updated", "updated",
        ]
    )


def sync_cuota_after_payment_change(cuota, user):
    if cuota.estado == "anulada" or not cuota.activo:
        return
    if cuota.valor_pagado >= cuota.valor:
        cuota.estado = "pagada"
    elif cuota.valor_pagado > 0:
        cuota.estado = "parcial"
    else:
        cuota.estado = "vencida" if cuota.fecha_pago_debito < timezone.localdate() else "pendiente"
    cuota.usuario_updated = user
    cuota.save(update_fields=["valor_pagado", "estado", "usuario_updated", "updated"])


def sync_plan_after_payment_change(plan, user):
    plan.saldo = max(plan.valor_total - plan.descuento - plan.abono, Decimal("0.00"))
    if plan.estado != "anulado":
        plan.estado = "cerrado" if plan.saldo == 0 else "activo"
    plan.usuario_updated = user
    plan.save(update_fields=["abono", "saldo", "estado", "usuario_updated", "updated"])
    ficha = FichaInscripcion.objects.select_for_update().get(pk=plan.ficha_inscripcion_id)
    sync_ficha_payment_summary(ficha, plan, user)


def move_payment_between_cuotas(payment_id, target_cuota_id, user):
    """Move an existing payment and keep both installments and plans balanced."""
    previous = Pago.objects.select_for_update().get(pk=payment_id)
    if previous.anulado or previous.cuota_id == target_cuota_id:
        return

    cuota_ids = sorted({previous.cuota_id, target_cuota_id})
    cuotas = {
        cuota.pk: cuota
        for cuota in Cuota.objects.select_for_update()
        .select_related("plan_pago")
        .filter(pk__in=cuota_ids)
        .order_by("pk")
    }
    old_cuota = cuotas[previous.cuota_id]
    target_cuota = cuotas[target_cuota_id]
    old_cuota.valor_pagado = max(
        old_cuota.valor_pagado - previous.valor,
        Decimal("0.00"),
    )
    target_cuota.valor_pagado += previous.valor
    sync_cuota_after_payment_change(old_cuota, user)
    sync_cuota_after_payment_change(target_cuota, user)

    plan_ids = sorted({old_cuota.plan_pago_id, target_cuota.plan_pago_id})
    plans = {
        plan.pk: plan
        for plan in PlanPago.objects.select_for_update()
        .filter(pk__in=plan_ids)
        .order_by("pk")
    }
    if old_cuota.plan_pago_id != target_cuota.plan_pago_id:
        old_plan = plans[old_cuota.plan_pago_id]
        target_plan = plans[target_cuota.plan_pago_id]
        old_plan.abono = max(old_plan.abono - previous.valor, Decimal("0.00"))
        target_plan.abono += previous.valor
        sync_plan_after_payment_change(old_plan, user)
        sync_plan_after_payment_change(target_plan, user)
    else:
        sync_plan_after_payment_change(plans[old_cuota.plan_pago_id], user)
