from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.core.forms import BootstrapFormMixin
from apps.core.models import Partner
from apps.cartera.models import FormaPago

from .models import Aula, Curso, FichaInscripcion, PeriodoAcademico


class PeriodoAcademicoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PeriodoAcademico
        fields = ["empresa", "nombre", "regimen", "fecha_inicio", "fecha_fin", "estado", "activo"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }


class CursoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Curso
        fields = ["empresa", "nombre", "grado", "carrera", "universidad", "activo"]


class AulaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Aula
        fields = [
            "empresa",
            "periodo_academico",
            "nombre",
            "seccion",
            "jornada",
            "horario",
            "hora",
            "duracion",
            "capacidad",
            "activo",
        ]


class FichaInscripcionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FichaInscripcion
        fields = [
            "empresa",
            "numero",
            "fecha",
            "periodo_academico",
            "curso",
            "aula",
            "cliente",
            "estudiante",
            "representante",
            "edad",
            "colegio",
            "curso_grado",
            "nota_grado",
            "carrera",
            "universidad",
            "nombre_conyuge",
            "ocupacion_conyuge",
            "correo_estudiante",
            "correo_representante",
            "horario",
            "hora",
            "duracion",
            "forma_pago_convenio",
            "fecha_proximo_pago",
            "valor_proximo_pago",
            "valor_total_curso",
            "valor_matricula",
            "descuento",
            "abono",
            "saldo",
            "promo",
            "autorizacion_imagen",
            "acepta_garantia",
            "acepta_no_devolucion",
            "estado",
            "observacion",
            "archivo_contrato",
            "archivo_ficha_firmada",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "fecha_proximo_pago": forms.DateInput(attrs={"type": "date"}),
            "correo_estudiante": forms.Textarea(attrs={"rows": 2}),
            "correo_representante": forms.Textarea(attrs={"rows": 2}),
            "observacion": forms.Textarea(attrs={"rows": 3}),
        }


class MatriculaProcesoForm(BootstrapFormMixin, forms.Form):
    FORMAS_PAGO_CONVENIO = FichaInscripcion.FORMA_PAGO_CONVENIO_CHOICES
    MODO_CHOICES = (
        ("seleccionar", "Seleccionar existente"),
        ("crear", "Crear nuevo"),
    )

    estudiante_modo = forms.ChoiceField(
        label="Estudiante",
        choices=MODO_CHOICES,
        initial="seleccionar",
        widget=forms.RadioSelect(attrs={"class": "mode-options"}),
    )
    estudiante_partner = forms.ModelChoiceField(
        label="Seleccionar estudiante",
        queryset=Partner.objects.none(),
        required=False,
    )
    estudiante_identificacion = forms.CharField(label="C.I. estudiante", max_length=20, required=False)
    estudiante_nombre = forms.CharField(label="Nombre estudiante", max_length=200, required=False)
    estudiante_fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento estudiante",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    estudiante_email = forms.EmailField(label="Correo estudiante", required=False)
    estudiante_telefono = forms.CharField(label="Celular estudiante", max_length=50, required=False)
    colegio = forms.CharField(max_length=200, required=False)
    curso_grado = forms.CharField(label="Curso/Grado", max_length=120, required=False)

    representante_modo = forms.ChoiceField(
        label="Representante",
        choices=MODO_CHOICES,
        initial="seleccionar",
        widget=forms.RadioSelect(attrs={"class": "mode-options"}),
    )
    representante_partner = forms.ModelChoiceField(
        label="Seleccionar representante",
        queryset=Partner.objects.none(),
        required=False,
    )
    representante_identificacion = forms.CharField(label="R.U.C./C.I. representante", max_length=20, required=False)
    representante_nombre = forms.CharField(label="Nombre representante", max_length=200, required=False)
    representante_telefono = forms.CharField(label="Telefono representante", max_length=50, required=False)
    representante_celular = forms.CharField(label="Celular representante", max_length=50, required=False)
    representante_email = forms.EmailField(label="Correo representante", required=False)
    representante_ocupacion = forms.CharField(label="Ocupacion representante", max_length=100, required=False)
    representante_direccion = forms.CharField(label="Direccion", max_length=200, required=False)

    numero = forms.CharField(label="No. ficha", max_length=30, required=False)
    fecha = forms.DateField(label="Fecha", widget=forms.DateInput(attrs={"type": "date"}))
    periodo_academico = forms.ModelChoiceField(label="Periodo", queryset=PeriodoAcademico.objects.none())
    curso = forms.ModelChoiceField(queryset=Curso.objects.none(), required=False)
    aula = forms.ModelChoiceField(queryset=Aula.objects.none(), required=False)
    edad = forms.IntegerField(
        required=False,
        min_value=0,
        disabled=True,
        widget=forms.NumberInput(attrs={"readonly": "readonly"}),
    )
    nota_grado = forms.CharField(label="Nota de grado", max_length=60, required=False)
    carrera = forms.CharField(max_length=160, required=False)
    universidad = forms.CharField(max_length=160, required=False)
    nombre_conyuge = forms.CharField(label="Nombre conyuge", max_length=200, required=False)
    ocupacion_conyuge = forms.CharField(label="Ocupacion conyuge", max_length=120, required=False)
    horario = forms.CharField(max_length=120, required=False)
    hora = forms.CharField(max_length=80, required=False)
    duracion = forms.CharField(max_length=80, required=False)

    forma_pago_convenio = forms.ChoiceField(label="Convenio", choices=FORMAS_PAGO_CONVENIO)
    valor_total_curso = forms.DecimalField(label="Valor total del curso", max_digits=12, decimal_places=2, min_value=0)
    valor_matricula = forms.DecimalField(label="Valor de matricula", max_digits=12, decimal_places=2, min_value=0, initial=0)
    descuento = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, initial=0)
    abono = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, initial=0)
    forma_pago_abono = forms.ModelChoiceField(
        label="Forma de pago del abono",
        queryset=FormaPago.objects.none(),
        required=False,
    )
    numero_documento_abono = forms.CharField(label="No. recibo/factura/deposito", max_length=60, required=False)
    numero_cuotas = forms.IntegerField(label="Numero de cuotas", min_value=1, initial=1)
    fecha_inicio_cobro = forms.DateField(label="Fecha primera cuota", widget=forms.DateInput(attrs={"type": "date"}))
    promo = forms.BooleanField(required=False)
    autorizacion_imagen = forms.BooleanField(label="Autoriza uso de imagen", required=False)
    acepta_garantia = forms.BooleanField(label="Acepta garantia", required=False)
    acepta_no_devolucion = forms.BooleanField(label="Acepta no devolucion", required=False)
    observacion = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields["estudiante_partner"].queryset = Partner.objects.filter(
                empresa=empresa,
                es_estudiante=True,
                activo=True,
            ).order_by("nombre")
            self.fields["representante_partner"].queryset = Partner.objects.filter(
                empresa=empresa,
                es_representante=True,
                activo=True,
            ).order_by("nombre")
            self.fields["periodo_academico"].queryset = PeriodoAcademico.objects.filter(empresa=empresa, activo=True)
            self.fields["curso"].queryset = Curso.objects.filter(empresa=empresa, activo=True)
            self.fields["aula"].queryset = Aula.objects.filter(empresa=empresa, activo=True)
            self.fields["forma_pago_abono"].queryset = FormaPago.objects.filter(empresa=empresa, activo=True, es_pago=True)
        else:
            self.fields["estudiante_partner"].queryset = Partner.objects.filter(es_estudiante=True, activo=True).order_by("nombre")
            self.fields["representante_partner"].queryset = Partner.objects.filter(es_representante=True, activo=True).order_by("nombre")
            self.fields["periodo_academico"].queryset = PeriodoAcademico.objects.filter(activo=True)
            self.fields["curso"].queryset = Curso.objects.filter(activo=True)
            self.fields["aula"].queryset = Aula.objects.filter(activo=True)
            self.fields["forma_pago_abono"].queryset = FormaPago.objects.filter(activo=True, es_pago=True)

    def clean(self):
        cleaned_data = super().clean()
        self.clean_estudiante(cleaned_data)
        self.clean_representante(cleaned_data)
        fecha_nacimiento = cleaned_data.get("estudiante_fecha_nacimiento")
        cleaned_data["edad"] = calcular_edad(fecha_nacimiento)
        valor_total_curso = cleaned_data.get("valor_total_curso") or 0
        valor_matricula = cleaned_data.get("valor_matricula") or 0
        descuento = cleaned_data.get("descuento") or 0
        abono = cleaned_data.get("abono") or 0
        saldo = valor_total_curso + valor_matricula - descuento - abono
        if saldo < 0:
            self.add_error("abono", "El abono no puede ser mayor que el total menos descuento.")
        if abono > 0 and not cleaned_data.get("forma_pago_abono"):
            self.add_error("forma_pago_abono", "Seleccione la forma de pago del abono.")
        return cleaned_data

    def clean_estudiante(self, cleaned_data):
        if "estudiante_modo" not in self.fields:
            return
        modo = cleaned_data.get("estudiante_modo")
        partner = cleaned_data.get("estudiante_partner")
        if modo == "seleccionar":
            if not partner:
                self.add_error("estudiante_partner", "Seleccione un estudiante activo.")
                return
            cleaned_data["estudiante_identificacion"] = partner.identificacion
            cleaned_data["estudiante_nombre"] = partner.nombre
            cleaned_data["estudiante_fecha_nacimiento"] = partner.fecha_nacimiento
            cleaned_data["estudiante_email"] = partner.email
            cleaned_data["estudiante_telefono"] = partner.telefono_celular
            return
        if not cleaned_data.get("estudiante_identificacion"):
            self.add_error("estudiante_identificacion", "Ingrese la identificacion del estudiante.")
        if not cleaned_data.get("estudiante_nombre"):
            self.add_error("estudiante_nombre", "Ingrese el nombre del estudiante.")

    def clean_representante(self, cleaned_data):
        if "representante_modo" not in self.fields:
            return
        modo = cleaned_data.get("representante_modo")
        partner = cleaned_data.get("representante_partner")
        if modo == "seleccionar":
            if not partner:
                self.add_error("representante_partner", "Seleccione un representante activo.")
                return
            conyuge = representante_conyuge_data(partner)
            cleaned_data["representante_identificacion"] = partner.identificacion
            cleaned_data["representante_nombre"] = partner.nombre
            cleaned_data["representante_email"] = partner.email
            cleaned_data["representante_telefono"] = partner.telefono
            cleaned_data["representante_celular"] = partner.telefono_celular
            cleaned_data["representante_ocupacion"] = partner.ocupacion
            cleaned_data["representante_direccion"] = partner.direccion
            cleaned_data["nombre_conyuge"] = cleaned_data.get("nombre_conyuge") or conyuge["nombre_conyuge"]
            cleaned_data["ocupacion_conyuge"] = cleaned_data.get("ocupacion_conyuge") or conyuge["ocupacion_conyuge"]
            return
        if not cleaned_data.get("representante_identificacion"):
            self.add_error("representante_identificacion", "Ingrese la identificacion del representante.")
        if not cleaned_data.get("representante_nombre"):
            self.add_error("representante_nombre", "Ingrese el nombre del representante.")


def calcular_edad(fecha_nacimiento):
    if not fecha_nacimiento:
        return None
    hoy = timezone.localdate()
    edad = hoy.year - fecha_nacimiento.year
    if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        edad -= 1
    return edad


def representante_conyuge_data(partner):
    tags = partner.tags or {}
    nombre_conyuge = tags.get("nombre_conyuge") or ""
    ocupacion_conyuge = tags.get("ocupacion_conyuge") or ""
    if nombre_conyuge or ocupacion_conyuge:
        return {
            "nombre_conyuge": nombre_conyuge,
            "ocupacion_conyuge": ocupacion_conyuge,
        }

    ficha = (
        FichaInscripcion.objects.filter(representante=partner)
        .filter(
            Q(nombre_conyuge__isnull=False, nombre_conyuge__gt="")
            | Q(ocupacion_conyuge__isnull=False, ocupacion_conyuge__gt="")
        )
        .order_by("-fecha", "-id")
        .first()
    )
    if not ficha:
        return {"nombre_conyuge": "", "ocupacion_conyuge": ""}
    return {
        "nombre_conyuge": ficha.nombre_conyuge or "",
        "ocupacion_conyuge": ficha.ocupacion_conyuge or "",
    }


class MatriculaPasoForm(MatriculaProcesoForm):
    field_names = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in list(self.fields):
            if field_name not in self.field_names:
                self.fields.pop(field_name)


class MatriculaEstudianteForm(MatriculaPasoForm):
    field_names = (
        "estudiante_modo",
        "estudiante_partner",
        "estudiante_identificacion",
        "estudiante_nombre",
        "estudiante_fecha_nacimiento",
        "edad",
        "estudiante_telefono",
        "estudiante_email",
    )


class MatriculaRepresentanteForm(MatriculaPasoForm):
    field_names = (
        "representante_modo",
        "representante_partner",
        "representante_identificacion",
        "representante_nombre",
        "representante_telefono",
        "representante_celular",
        "representante_email",
        "representante_ocupacion",
        "representante_direccion",
        "nombre_conyuge",
        "ocupacion_conyuge",
    )


class MatriculaDatosForm(MatriculaPasoForm):
    field_names = (
        "numero",
        "fecha",
        "periodo_academico",
        "curso",
        "aula",
        "colegio",
        "curso_grado",
        "nota_grado",
        "horario",
        "hora",
        "duracion",
        "carrera",
        "universidad",
    )


class MatriculaConvenioForm(MatriculaPasoForm):
    field_names = (
        "forma_pago_convenio",
        "valor_total_curso",
        "valor_matricula",
        "descuento",
        "abono",
        "forma_pago_abono",
        "numero_documento_abono",
        "numero_cuotas",
        "fecha_inicio_cobro",
        "promo",
        "autorizacion_imagen",
        "acepta_garantia",
        "acepta_no_devolucion",
        "observacion",
    )
