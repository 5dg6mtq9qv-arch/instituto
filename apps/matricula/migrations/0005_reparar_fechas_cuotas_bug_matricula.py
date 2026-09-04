from calendar import monthrange
from datetime import timedelta

from django.db import migrations
from django.utils import timezone


AFFECTED_FICHAS = (
    (1, "000001"),
    (2, "000002"),
    (3, "000003"),
    (4, "000004"),
    (5, "000005"),
    (6, "000006"),
    (7, "000007"),
    (8, "000008"),
    (9, "000009"),
    (10, "000010"),
    (17, "000017"),
    (18, "000018"),
    (21, "000021"),
    (22, "000022"),
    (23, "000023"),
    (26, "000026"),
    (27, "000027"),
    (28, "000028"),
    (29, "000029"),
    (30, "000030"),
    (31, "000031"),
    (32, "000032"),
    (34, "000034"),
    (35, "000035"),
    (37, "000037"),
    (38, "000038"),
    (42, "000042"),
    (43, "000043"),
    (44, "000044"),
    (45, "000045"),
    (46, "000046"),
    (48, "000048"),
    (50, "000050"),
    (51, "000051"),
    (52, "000052"),
    (54, "000054"),
    (56, "000056"),
    (57, "000057"),
    (60, "000060"),
    (61, "000061"),
    (63, "000063"),
    (64, "000064"),
)

PROXIMO_PAGO_ONLY = (
    (47, "000047"),
    (59, "000059"),
)


def add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def fecha_cuota(base_date, convenio, numero):
    if numero <= 0:
        return base_date
    if convenio == "quincenal":
        return base_date + timedelta(days=15 * (numero - 1))
    return add_months(base_date, numero - 1)


def estado_pendiente(cuota):
    if cuota.estado in {"pagada", "anulada"}:
        return cuota.estado
    return "parcial" if cuota.valor_pagado > 0 else "pendiente"


def proximo_pago(cuotas):
    for cuota in sorted(cuotas, key=lambda item: (item.fecha_pago_debito, item.numero, item.pk)):
        if not cuota.activo or cuota.estado in {"pagada", "anulada"}:
            continue
        saldo = cuota.valor - cuota.valor_pagado
        if saldo > 0:
            return cuota.fecha_pago_debito, saldo
    return None, 0


def repair_ficha_dates(apps, schema_editor):
    FichaInscripcion = apps.get_model("matricula", "FichaInscripcion")
    PlanPago = apps.get_model("cartera", "PlanPago")
    Cuota = apps.get_model("cartera", "Cuota")

    for ficha_id, numero in AFFECTED_FICHAS:
        try:
            ficha = FichaInscripcion.objects.get(pk=ficha_id, numero=numero)
        except FichaInscripcion.DoesNotExist:
            continue

        created_date = timezone.localtime(ficha.created).date()
        base_date = max(ficha.fecha, created_date)
        plan = PlanPago.objects.filter(ficha_inscripcion_id=ficha.pk).first()
        if not plan:
            continue

        cuotas = list(Cuota.objects.filter(plan_pago_id=plan.pk).order_by("numero", "pk"))
        for cuota in cuotas:
            cuota.fecha_pago_debito = fecha_cuota(base_date, ficha.forma_pago_convenio, cuota.numero)
            cuota.estado = estado_pendiente(cuota)
            cuota.save(update_fields=["fecha_pago_debito", "estado"])

        ficha.fecha = base_date
        ficha.fecha_proximo_pago, ficha.valor_proximo_pago = proximo_pago(cuotas)
        ficha.save(update_fields=["fecha", "fecha_proximo_pago", "valor_proximo_pago"])

    for ficha_id, numero in PROXIMO_PAGO_ONLY:
        try:
            ficha = FichaInscripcion.objects.get(pk=ficha_id, numero=numero)
        except FichaInscripcion.DoesNotExist:
            continue

        plan = PlanPago.objects.filter(ficha_inscripcion_id=ficha.pk).first()
        if not plan:
            continue
        cuotas = list(Cuota.objects.filter(plan_pago_id=plan.pk).order_by("fecha_pago_debito", "numero", "pk"))
        ficha.fecha_proximo_pago, ficha.valor_proximo_pago = proximo_pago(cuotas)
        ficha.save(update_fields=["fecha_proximo_pago", "valor_proximo_pago"])


class Migration(migrations.Migration):
    dependencies = [
        ("cartera", "0001_initial"),
        ("matricula", "0004_rename_pago_unico_label"),
    ]

    operations = [
        migrations.RunPython(repair_ficha_dates, migrations.RunPython.noop),
    ]
