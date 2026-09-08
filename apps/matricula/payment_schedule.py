from calendar import monthrange
from datetime import timedelta


def add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def fecha_cuota(fecha_primera_cuota, forma_pago_convenio, numero):
    if forma_pago_convenio == "quincenal":
        return fecha_primera_cuota + timedelta(days=15 * (numero - 1))
    return add_months(fecha_primera_cuota, numero - 1)
