from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "institution",
        "role",
        "is_active",
    )
    list_filter = ("role", "institution", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email", "phone")
    fieldsets = UserAdmin.fieldsets + (
        ("Institutional data", {"fields": ("institution", "role", "phone")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Institutional data", {"fields": ("institution", "role", "phone")}),
    )

# Register your models here.
