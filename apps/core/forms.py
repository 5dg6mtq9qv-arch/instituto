from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import Group, Permission

from .models import Empresa, Partner, TipoIdentificacion


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                if field_name in {"activo", "activa", "is_active"}:
                    add_widget_class(widget, "js-switch")
                else:
                    widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                pass
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")
                if isinstance(widget, forms.DateInput) and not isinstance(widget, forms.DateTimeInput):
                    add_widget_class(widget, "js-date-picker")
                    widget.attrs.setdefault("autocomplete", "off")
                    widget.attrs.setdefault("placeholder", "dd/mm/aaaa")


def add_widget_class(widget, class_name):
    current_class = widget.attrs.get("class", "")
    classes = current_class.split()
    if class_name not in classes:
        classes.append(class_name)
        widget.attrs["class"] = " ".join(classes).strip()


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


class MiPerfilPartnerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Partner
        fields = [
            "foto",
            "nombre",
            "direccion",
            "telefono",
            "telefono_celular",
            "email",
            "fecha_nacimiento",
            "genero",
            "ocupacion",
        ]
        widgets = {
            "nombre": forms.Textarea(attrs={"rows": 2}),
            "email": forms.Textarea(attrs={"rows": 2}),
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }


class MiPerfilPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    old_password = forms.CharField(
        label="Contraseña actual",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password1 = forms.CharField(
        label="Nueva contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )


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
        self.fields["permissions"].label_from_instance = self.permission_label
        self.fields["users"].queryset = get_user_model().objects.filter(is_active=True).order_by("username")
        if self.instance.pk:
            self.fields["users"].initial = self.instance.user_set.all()

    @staticmethod
    def permission_label(permission):
        content_type = permission.content_type
        schema = content_type.app_label.replace("_", " ").title()
        model = content_type.model.replace("_", " ").title()
        return f"{schema} / {model} / {permission.name}"

    def save(self, commit=True):
        group = super().save(commit=commit)
        if commit:
            group.user_set.set(self.cleaned_data["users"])
        return group


class SystemUserForm(BootstrapFormMixin, forms.ModelForm):
    password = forms.CharField(
        label="Contraseña",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}, render_value=False),
        help_text="En edición puedes dejarla vacía para conservar la contraseña actual.",
    )
    groups = forms.ModelMultipleChoiceField(
        label="Grupos",
        queryset=Group.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "d-none", "data-group-hidden": "true"}),
    )

    class Meta:
        model = get_user_model()
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "groups",
            "password",
        ]
        labels = {
            "username": "Usuario",
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "email": "Correo",
            "is_active": "Activo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_password_hash = self.instance.password if self.instance.pk else ""
        self.fields["groups"].queryset = Group.objects.order_by("name")
        if self.instance.pk:
            self.fields["groups"].initial = self.instance.groups.all()
            self.fields["password"].label = "Nueva contraseña"
            self.fields["password"].widget.attrs.setdefault("placeholder", "Contraseña actual protegida")
        else:
            self.fields["password"].required = True

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not self.instance.pk and not password:
            raise forms.ValidationError("La contraseña es obligatoria para crear un usuario.")
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        elif self.current_password_hash:
            user.password = self.current_password_hash
        if commit:
            user.save()
            user.groups.set(self.cleaned_data["groups"])
            self.save_docente_partner(user)
        return user

    def save_docente_partner(self, user):
        groups = self.cleaned_data.get("groups")
        is_docente_group = groups.filter(name__iexact="Docente").exists() if groups is not None else False
        if not is_docente_group:
            return

        identificacion = user.username[:20]
        partner = getattr(user, "partner", None)
        if partner is None:
            partner = Partner.objects.filter(identificacion=identificacion).first()
        if partner is None:
            tipo_identificacion = TipoIdentificacion.objects.filter(activo=True).order_by("id").first()
            if tipo_identificacion is None:
                tipo_identificacion = TipoIdentificacion.objects.create(nombre="Cedula", codigo="CED")
            partner = Partner(tipo_identificacion=tipo_identificacion, identificacion=identificacion)

        nombre = user.get_full_name() or user.username
        partner.nombre = nombre
        partner.email = user.email or partner.email
        partner.usuario = user
        partner.es_docente = True
        partner.activo = True
        partner.save()
