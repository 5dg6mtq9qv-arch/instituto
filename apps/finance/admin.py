from django.contrib import admin

from .models import Installment, Payment, PaymentPlan


class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "total_amount", "discount_amount", "status", "generated_by")
    list_filter = ("status", "enrollment__institution")
    search_fields = ("enrollment__student__first_names", "enrollment__student__last_names", "enrollment__student__document_number")
    inlines = [InstallmentInline]


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = ("payment_plan", "number", "due_date", "amount", "paid_amount", "status", "priority")
    list_filter = ("status", "priority", "due_date")
    search_fields = ("payment_plan__enrollment__student__first_names", "payment_plan__enrollment__student__last_names")
    date_hierarchy = "due_date"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("installment", "paid_at", "amount", "method", "receipt_number", "registered_by")
    list_filter = ("method", "paid_at")
    search_fields = ("receipt_number", "installment__payment_plan__enrollment__student__first_names", "installment__payment_plan__enrollment__student__last_names")
    date_hierarchy = "paid_at"

# Register your models here.
