from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.core.forms import BootstrapFormMixin
from apps.core.models import Partner
from apps.cartera.forms import pago_comprobante_duplicado, pago_comprobante_duplicado_message
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
        labels = {
            "valor_proximo_pago": "Valor de cuota",
            "saldo": "Restante",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["numero"].disabled = True
        self.fields["numero"].widget.attrs["readonly"] = "readonly"
        self.fields["numero"].widget.attrs["aria-readonly"] = "true"


class MatriculaProcesoForm(BootstrapFormMixin, forms.Form):
    FORMAS_PAGO_CONVENIO = FichaInscripcion.FORMA_PAGO_CONVENIO_CHOICES
    MODO_CHOICES = (
        ("seleccionar", "Seleccionar existente"),
        ("crear", "Crear nuevo"),
    )

    estudiante_modo = forms.ChoiceField(
        label="Registro del estudiante",
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
        label="Registro del representante",
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
    periodo_academico = forms.ModelChoiceField(label="Periodo", queryset=PeriodoAcademico.objects.none(), required=False)
    curso = forms.ModelChoiceField(
        label="Curso",
        queryset=Curso.objects.none(),
        required=False,
    )
    aula = forms.ModelChoiceField(
        label="Aula",
        queryset=Aula.objects.none(),
        required=False,
    )
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
    valor_cuota = forms.DecimalField(label="Valor de cuota", max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    valor_total_curso = forms.DecimalField(
        label="Valor total del curso",
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        initial=0,
    )
    valor_matricula = forms.DecimalField(
        label="Valor de matricula",
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        initial=0,
    )
    descuento = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, initial=0)
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
        self.estudiante_guardado_id = kwargs.pop("estudiante_guardado_id", None)
        self.representante_guardado_id = kwargs.pop("representante_guardado_id", None)
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        if empresa:
            estudiantes = Partner.objects.filter(
                empresa=empresa,
                es_estudiante=True,
                activo=True,
            ).order_by("nombre")
            representantes = Partner.objects.filter(
                empresa=empresa,
                es_representante=True,
                activo=True,
            ).order_by("nombre")
            periodos = PeriodoAcademico.objects.filter(empresa=empresa, activo=True)
            cursos = Curso.objects.filter(empresa=empresa, activo=True)
            aulas = Aula.objects.filter(empresa=empresa, activo=True)
            self.fields["forma_pago_abono"].queryset = FormaPago.objects.filter(empresa=empresa, activo=True, es_pago=True)
        else:
            estudiantes = Partner.objects.filter(es_estudiante=True, activo=True).order_by("nombre")
            representantes = Partner.objects.filter(es_representante=True, activo=True).order_by("nombre")
            periodos = PeriodoAcademico.objects.filter(activo=True)
            cursos = Curso.objects.filter(activo=True)
            aulas = Aula.objects.filter(activo=True)
            self.fields["forma_pago_abono"].queryset = FormaPago.objects.filter(activo=True, es_pago=True)

        periodo_id = self.selected_periodo_id()
        if periodo_id:
            aulas = aulas.filter(periodo_academico_id=periodo_id)

        self.fields["estudiante_partner"].queryset = estudiantes
        self.fields["representante_partner"].queryset = representantes
        self.fields["periodo_academico"].queryset = periodos.order_by("-fecha_inicio", "nombre")
        self.fields["curso"].queryset = cursos.order_by("nombre")
        self.fields["aula"].queryset = aulas.select_related("periodo_academico").order_by(
            "periodo_academico",
            "nombre",
            "seccion",
        )

        self.fields["estudiante_partner"].empty_label = "Seleccione estudiante registrado"
        self.fields["representante_partner"].empty_label = "Seleccione representante registrado"
        self.fields["periodo_academico"].empty_label = "Asignar luego"
        self.fields["curso"].empty_label = "Asignar luego"
        self.fields["aula"].empty_label = "Asignar luego"
        self.fields["curso"].label_from_instance = self.curso_label
        self.fields["aula"].label_from_instance = self.aula_label

        if not self.is_bound and not self.initial.get("estudiante_modo") and not estudiantes.exists():
            self.fields["estudiante_modo"].initial = "crear"
        if not self.is_bound and not self.initial.get("representante_modo") and not representantes.exists():
            self.fields["representante_modo"].initial = "crear"

        self.fields["periodo_academico"].widget.attrs["data-periodo-select"] = "true"
        self.fields["numero"].disabled = True
        self.fields["numero"].widget.attrs["readonly"] = "readonly"
        self.fields["numero"].widget.attrs["aria-readonly"] = "true"
        self.fields["curso"].widget.attrs["data-curso-select"] = "true"
        self.fields["aula"].widget.attrs["data-aula-select"] = "true"
        self.fields["horario"].widget.attrs["data-aula-horario"] = "horario"
        self.fields["hora"].widget.attrs["data-aula-horario"] = "hora"
        self.fields["duracion"].widget.attrs["data-aula-horario"] = "duracion"
        self.fields["valor_cuota"].widget.attrs["data-money-input"] = "cuota"
        self.fields["abono"].widget.attrs["data-money-input"] = "abono"
        self.fields["numero_cuotas"].widget.attrs["data-installments-input"] = "true"

    def selected_periodo_id(self):
        if self.is_bound:
            value = self.data.get(self.add_prefix("periodo_academico"))
        else:
            value = self.initial.get("periodo_academico")
        if hasattr(value, "pk"):
            return value.pk
        return value or None

    @staticmethod
    def curso_label(curso):
        details = [curso.grado, curso.carrera, curso.universidad]
        detail_text = " / ".join(detail for detail in details if detail)
        return f"{curso.nombre} - {detail_text}" if detail_text else curso.nombre

    @staticmethod
    def aula_label(aula):
        detail = " ".join(part for part in [aula.seccion, aula.jornada] if part)
        schedule = " / ".join(part for part in [aula.horario, aula.hora] if part)
        suffix = " - ".join(part for part in [detail, schedule] if part)
        return f"{aula.nombre} - {suffix}" if suffix else aula.nombre

    def clean(self):
        cleaned_data = super().clean()
        self.clean_estudiante(cleaned_data)
        self.clean_representante(cleaned_data)
        self.clean_identificaciones_distintas(cleaned_data)
        self.clean_matricula(cleaned_data)
        fecha_nacimiento = cleaned_data.get("estudiante_fecha_nacimiento")
        cleaned_data["edad"] = calcular_edad(fecha_nacimiento)
        valor_cuota = cleaned_data.get("valor_cuota") or 0
        numero_cuotas = cleaned_data.get("numero_cuotas") or 0
        abono = cleaned_data.get("abono") or 0
        saldo = valor_cuota * numero_cuotas
        cleaned_data["saldo_calculado"] = saldo
        cleaned_data["valor_total_curso"] = saldo + abono
        cleaned_data["valor_matricula"] = Decimal("0.00")
        cleaned_data["descuento"] = Decimal("0.00")
        if abono > 0 and not cleaned_data.get("forma_pago_abono"):
            self.add_error("forma_pago_abono", "Seleccione la forma de pago del abono.")
        self.clean_comprobante_abono(cleaned_data)
        return cleaned_data

    def partner_identificacion_duplicada(self, identificacion, exclude_pk=None):
        identificacion = (identificacion or "").strip()
        if not identificacion:
            return None
        partners = Partner.objects.filter(identificacion__iexact=identificacion)
        if exclude_pk:
            partners = partners.exclude(pk=exclude_pk)
        return partners.first()

    def clean_matricula(self, cleaned_data):
        if "periodo_academico" not in self.fields:
            return
        periodo = cleaned_data.get("periodo_academico")
        curso = cleaned_data.get("curso")
        aula = cleaned_data.get("aula")

        if periodo and aula and aula.periodo_academico_id != periodo.pk:
            self.add_error("aula", "El aula seleccionada no pertenece al periodo academico.")

        if curso:
            cleaned_data["curso_grado"] = cleaned_data.get("curso_grado") or curso.grado or ""
            cleaned_data["carrera"] = cleaned_data.get("carrera") or curso.carrera or ""
            cleaned_data["universidad"] = cleaned_data.get("universidad") or curso.universidad or ""

        if aula:
            cleaned_data["horario"] = cleaned_data.get("horario") or aula.horario or ""
            cleaned_data["hora"] = cleaned_data.get("hora") or aula.hora or ""
            cleaned_data["duracion"] = cleaned_data.get("duracion") or aula.duracion or ""

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
        identificacion = (cleaned_data.get("estudiante_identificacion") or "").strip()
        cleaned_data["estudiante_identificacion"] = identificacion
        if not identificacion:
            self.add_error("estudiante_identificacion", "Ingrese la identificacion del estudiante.")
        elif self.partner_identificacion_duplicada(identificacion, self.estudiante_guardado_id):
            self.add_error(
                "estudiante_identificacion",
                "Ya existe un registro con esta identificacion. Seleccione el estudiante registrado en lugar de crear uno nuevo.",
            )
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
        identificacion = (cleaned_data.get("representante_identificacion") or "").strip()
        cleaned_data["representante_identificacion"] = identificacion
        if not identificacion:
            self.add_error("representante_identificacion", "Ingrese la identificacion del representante.")
        elif self.partner_identificacion_duplicada(identificacion, self.representante_guardado_id):
            self.add_error(
                "representante_identificacion",
                "Ya existe un registro con esta identificacion. Seleccione el representante registrado en lugar de crear uno nuevo.",
            )
        if not cleaned_data.get("representante_nombre"):
            self.add_error("representante_nombre", "Ingrese el nombre del representante.")

    def clean_comprobante_abono(self, cleaned_data):
        if "numero_documento_abono" not in self.fields:
            return
        numero_documento = (cleaned_data.get("numero_documento_abono") or "").strip()
        cleaned_data["numero_documento_abono"] = numero_documento
        if not numero_documento or (cleaned_data.get("abono") or 0) <= 0:
            return
        pago_duplicado = pago_comprobante_duplicado(numero_documento, empresa=self.empresa)
        if pago_duplicado:
            self.add_error("numero_documento_abono", pago_comprobante_duplicado_message(pago_duplicado))

    def clean_identificaciones_distintas(self, cleaned_data):
        if "estudiante_identificacion" not in self.fields or "representante_identificacion" not in self.fields:
            return
        estudiante_identificacion = (cleaned_data.get("estudiante_identificacion") or "").strip().lower()
        representante_identificacion = (cleaned_data.get("representante_identificacion") or "").strip().lower()
        if estudiante_identificacion and estudiante_identificacion == representante_identificacion:
            self.add_error(
                "representante_identificacion",
                "La identificacion del representante no puede ser igual a la del estudiante.",
            )


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
        "colegio",
        "curso_grado",
        "nota_grado",
        "carrera",
        "universidad",
    )


class MatriculaConvenioForm(MatriculaPasoForm):
    field_names = (
        "forma_pago_convenio",
        "valor_cuota",
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
