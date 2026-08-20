from django.conf import settings
from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedModel


class PaymentPlan(SoftDeleteModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        ACTIVE = "active", "Activo"
        CLOSED = "closed", "Cerrado"
        CANCELLED = "cancelled", "Cancelado"

    enrollment = models.OneToOneField(
        "people.Enrollment",
        on_delete=models.PROTECT,
        related_name="payment_plan",
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="generated_payment_plans",
        blank=True,
        null=True,
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Plan {self.enrollment}"


class Installment(SoftDeleteModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PARTIAL = "partial", "Parcial"
        PAID = "paid", "Pagada"
        OVERDUE = "overdue", "Vencida"
        CANCELLED = "cancelled", "Cancelada"

    class Priority(models.TextChoices):
        LOW = "low", "Baja"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Alta"
        CRITICAL = "critical", "Critica"

    payment_plan = models.ForeignKey(
        PaymentPlan,
        on_delete=models.CASCADE,
        related_name="installments",
    )
    number = models.PositiveIntegerField()
    due_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
        db_index=True,
    )

    class Meta:
        ordering = ["due_date", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["payment_plan", "number"],
                name="uniq_installment_number_by_plan",
            )
        ]

    def __str__(self):
        return f"Cuota {self.number} - {self.payment_plan}"


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Efectivo"
        TRANSFER = "transfer", "Transferencia"
        CARD = "card", "Tarjeta"
        OTHER = "other", "Otro"

    installment = models.ForeignKey(
        Installment,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    paid_at = models.DateTimeField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.CASH,
    )
    receipt_number = models.CharField(max_length=60, unique=True, blank=True, null=True)
    proof = models.FileField(upload_to="payments/proofs/", blank=True, null=True)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="registered_payments",
        blank=True,
        null=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self):
        return f"Pago {self.amount} - {self.installment}"

# Create your models here.
