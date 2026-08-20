from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models import TimeStampedModel


class User(AbstractUser, TimeStampedModel):
    class Role(models.TextChoices):
        ADMINISTRATOR = "administrator", "Administrador"
        DIRECTION = "direction", "Direccion"
        COORDINATION = "coordination", "Coordinacion"
        TEACHER = "teacher", "Docente"

    institution = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.PROTECT,
        related_name="users",
        blank=True,
        null=True,
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.TEACHER,
        db_index=True,
    )
    phone = models.CharField(max_length=30, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["institution", "role"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        name = self.get_full_name() or self.username
        return f"{name} - {self.get_role_display()}"
