from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission

from .models import Empresa, Partner


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                pass
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class EmpresaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Empresa
        fields = [
            "ruc",
            "razon_social",
            "nombre_comercial",
            "direccion",
            "telefono",
            "email",
            "ciudad",
            "activa",
        ]
        widgets = {
            "direccion": forms.Textarea(attrs={"rows": 2}),
            "email": forms.Textarea(attrs={"rows": 2}),
        }


class PartnerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Partner
        fields = [
            "empresa",
            "tipo_identificacion",
            "identificacion",
            "nombre",
            "direccion",
            "telefono",
            "telefono_celular",
            "email",
            "fecha_nacimiento",
            "genero",
            "ocupacion",
            "es_cliente",
            "es_estudiante",
            "es_representante",
            "es_docente",
            "activo",
        ]
        widgets = {
            "nombre": forms.Textarea(attrs={"rows": 2}),
            "email": forms.Textarea(attrs={"rows": 2}),
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }


class GroupPermissionForm(BootstrapFormMixin, forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        label="Permisos",
        queryset=Permission.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    users = forms.ModelMultipleChoiceField(
        label="Usuarios del grupo",
        queryset=get_user_model().objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Group
        fields = ["name", "permissions", "users"]
        labels = {"name": "Nombre del grupo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        permission_queryset = (
            Permission.objects.select_related("content_type")
            .filter(
                content_type__app_label__in=[
                    "core",
                    "matricula",
                    "cartera",
                    "academico",
                    "auditoria",
                    "auth",
                ]
            )
            .order_by("content_type__app_label", "content_type__model", "codename")
        )
        self.fields["permissions"].queryset = permission_queryset
        self.fields["users"].queryset = get_user_model().objects.filter(is_active=True).order_by("username")
        if self.instance.pk:
            self.fields["users"].initial = self.instance.user_set.all()

    def save(self, commit=True):
        group = super().save(commit=commit)
        if commit:
            group.user_set.set(self.cleaned_data["users"])
        return group
