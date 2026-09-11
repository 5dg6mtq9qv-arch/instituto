from decimal import Decimal


def duration_to_minutes(value):
    duration = Decimal(value or 0).quantize(Decimal("0.01"))
    if duration < 0:
        raise ValueError("La duración no puede ser negativa.")
    hours = int(duration)
    minutes = int((duration - Decimal(hours)) * 100)
    if minutes >= 60:
        raise ValueError("Los minutos deben estar entre 00 y 59.")
    return hours * 60 + minutes


def minutes_to_duration(total_minutes):
    hours, minutes = divmod(int(total_minutes), 60)
    return Decimal(f"{hours}.{minutes:02d}")


def split_duration(value):
    return divmod(duration_to_minutes(value), 60)


def format_duration(value):
    hours, minutes = split_duration(value)
    return f"{hours}:{minutes:02d}"
