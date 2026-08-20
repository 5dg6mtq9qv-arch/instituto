from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import SoftDeleteModel, TimeStampedModel


class Student(SoftDeleteModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Activo"
        INACTIVE = "inactive", "Inactivo"
        WITHDRAWN = "withdrawn", "Retirado"
        GRADUATED = "graduated", "Graduado"

    institution = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.PROTECT,
        related_name="students",
    )
    document_type = models.CharField(max_length=20, default="cedula")
    document_number = models.CharField(max_length=30)
    first_names = models.CharField(max_length=120)
    last_names = models.CharField(max_length=120)
    birth_date = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )

    class Meta:
        ordering = ["last_names", "first_names"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "document_number"],
                condition=Q(is_deleted=False),
                name="uniq_active_student_document_by_institution",
            )
        ]

    @property
    def full_name(self):
        return f"{self.last_names} {self.first_names}".strip()

    def __str__(self):
        return self.full_name


class Representative(SoftDeleteModel):
    institution = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.PROTECT,
        related_name="representatives",
    )
    document_type = models.CharField(max_length=20, default="cedula")
    document_number = models.CharField(max_length=30)
    first_names = models.CharField(max_length=120)
    last_names = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30)
    secondary_phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["last_names", "first_names"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "document_number"],
                condition=Q(is_deleted=False),
                name="uniq_active_representative_document_by_institution",
            )
        ]

    @property
    def full_name(self):
        return f"{self.last_names} {self.first_names}".strip()

    def __str__(self):
        return self.full_name


class StudentRepresentative(TimeStampedModel):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="student_representatives",
    )
    representative = models.ForeignKey(
        Representative,
        on_delete=models.CASCADE,
        related_name="student_representatives",
    )
    relationship = models.CharField(max_length=60)
    is_primary = models.BooleanField(default=False)
    emergency_contact = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "representative"],
                name="uniq_student_representative",
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.representative}"


class Enrollment(SoftDeleteModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        ACTIVE = "active", "Activa"
        SUSPENDED = "suspended", "Suspendida"
        WITHDRAWN = "withdrawn", "Retirada"
        COMPLETED = "completed", "Completada"

    institution = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    academic_period = models.ForeignKey(
        "institutions.AcademicPeriod",
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    classroom = models.ForeignKey(
        "institutions.Classroom",
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    code = models.CharField(max_length=40, blank=True)
    enrollment_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    signed_document = models.FileField(
        upload_to="enrollments/signed/",
        blank=True,
        null=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-enrollment_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_period"],
                condition=Q(is_deleted=False),
                name="uniq_active_enrollment_by_student_period",
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.academic_period}"


class ClassroomHistory(TimeStampedModel):
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="classroom_history",
    )
    from_classroom = models.ForeignKey(
        "institutions.Classroom",
        on_delete=models.PROTECT,
        related_name="classroom_moves_from",
        blank=True,
        null=True,
    )
    to_classroom = models.ForeignKey(
        "institutions.Classroom",
        on_delete=models.PROTECT,
        related_name="classroom_moves_to",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="classroom_changes",
        blank=True,
        null=True,
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.enrollment} -> {self.to_classroom}"

# Create your models here.
