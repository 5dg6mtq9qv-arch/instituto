from django.db import models
from django.db.models import Q

from apps.common.models import SoftDeleteModel


class Institution(SoftDeleteModel):
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=180)
    legal_name = models.CharField(max_length=220, blank=True)
    tax_id = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AcademicPeriod(SoftDeleteModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        ACTIVE = "active", "Activo"
        CLOSED = "closed", "Cerrado"

    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        related_name="academic_periods",
    )
    name = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "name"],
                condition=Q(is_deleted=False),
                name="uniq_active_period_by_institution_name",
            )
        ]

    def __str__(self):
        return f"{self.institution} - {self.name}"


class Classroom(SoftDeleteModel):
    class Shift(models.TextChoices):
        MORNING = "morning", "Matutina"
        AFTERNOON = "afternoon", "Vespertina"
        NIGHT = "night", "Nocturna"
        WEEKEND = "weekend", "Fin de semana"

    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        related_name="classrooms",
    )
    academic_period = models.ForeignKey(
        AcademicPeriod,
        on_delete=models.PROTECT,
        related_name="classrooms",
    )
    name = models.CharField(max_length=120)
    section = models.CharField(max_length=40, blank=True)
    shift = models.CharField(max_length=20, choices=Shift.choices, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["academic_period", "name", "section"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "academic_period", "name", "section"],
                condition=Q(is_deleted=False),
                name="uniq_active_classroom_by_period",
            )
        ]

    def __str__(self):
        label = f"{self.name} {self.section}".strip()
        return f"{label} - {self.academic_period}"
