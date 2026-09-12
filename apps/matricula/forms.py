from decimal import Decimal

from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.forms import BootstrapFormMixin
from apps.core.models import Partner
from apps.cartera.forms import pago_comprobante_duplicado, pago_comprobante_duplicado_message
from apps.cartera.models import Cuota, FormaPago, PlanPago

from .models import Aula, Curso, FichaInscripcion, PeriodoAcademico
from .payment_schedule import fecha_cuota


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
    numero_cuotas = forms.IntegerField(
        label="Número de cuotas",
        min_value=1,
        required=False,
        help_text=(
            "Puedes agregar cuotas. Para reducirlas, las últimas cuotas deben estar sin pagos; "
            "se conservarán anuladas como historial."
        ),
    )
    valor_matricula = forms.DecimalField(
        label="Valor de matrícula", min_value=0, max_digits=12, decimal_places=2,
        required=False,
        help_text="Sin pagos registrados, crea o actualiza el rubro matrícula y ajusta el saldo automáticamente.",
    )
    estudiante_es_de_ibarra = forms.BooleanField(
        label="Es de Ibarra",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "js-switch"}),
    )

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
            "estudiante_es_de_ibarra",
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
            "numero_cuotas",
            "valor_matricula",
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
            "fecha_proximo_pago": "Fecha primera cuota",
            "valor_proximo_pago": "Valor de cuota",
            "saldo": "Restante",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_installment_count = 0
        self.installment_plan = None
        if self.instance.pk:
            self.installment_plan = PlanPago.objects.filter(
                ficha_inscripcion=self.instance,
                activo=True,
            ).first()
            if self.installment_plan:
                self.current_installment_count = (
                    self.installment_plan.cuotas.filter(numero__gt=0, activo=True)
                    .order_by("-numero")
                    .values_list("numero", flat=True)
                    .first()
                    or 0
                )
                self.initial.setdefault("numero_cuotas", self.current_installment_count or None)
        self.fields["numero"].disabled = True
        self.fields["numero"].widget.attrs["readonly"] = "readonly"
        self.fields["numero"].widget.attrs["aria-readonly"] = "true"
        self.fields["fecha_proximo_pago"].help_text = (
            "Al guardar, se recalcularán las fechas de todas las cuotas según el convenio."
        )
        if self.instance.pk and self.instance.estudiante_id:
            self.fields["estudiante_es_de_ibarra"].initial = self.instance.estudiante.es_de_ibarra
        self.payment_fields_locked = self.has_registered_payments()
        if self.payment_fields_locked:
            for field_name in [
                "forma_pago_convenio",
                "fecha_proximo_pago",
                "valor_proximo_pago",
                "valor_matricula",
                "abono",
                "saldo",
            ]:
                self.fields[field_name].disabled = True
                self.fields[field_name].widget.attrs["readonly"] = "readonly"
                self.fields[field_name].help_text = "Bloqueado porque esta ficha ya tiene pagos registrados."

    def has_registered_payments(self):
        if not self.instance.pk:
            return False
        try:
            return self.instance.plan_pago.cuotas.filter(pagos__isnull=False).exists()
        except ObjectDoesNotExist:
            return False

    def clean_valor_matricula(self):
        value = self.cleaned_data.get("valor_matricula")
        return self.initial.get("valor_matricula", Decimal("0.00")) if value is None else value

    def clean_numero_cuotas(self):
        value = self.cleaned_data.get("numero_cuotas")
        if value is None:
            return self.current_installment_count or None
        if not self.installment_plan:
            raise forms.ValidationError("La ficha necesita un plan de pago activo para modificar las cuotas.")
        if value < self.current_installment_count:
            cuotas_a_retirar = self.installment_plan.cuotas.filter(
                numero__gt=value,
                activo=True,
            )
            if cuotas_a_retirar.filter(Q(pagos__isnull=False) | Q(valor_pagado__gt=0)).exists():
                raise forms.ValidationError(
                    "No puedes reducir a ese número porque una de las últimas cuotas ya tiene pagos registrados."
                )
        if value > self.current_installment_count:
            cuota_referencia = (
                self.installment_plan.cuotas.filter(numero__gt=0)
                .order_by("numero")
                .first()
            )
            valor_referencia = (
                cuota_referencia.valor
                if cuota_referencia
                else self.cleaned_data.get("valor_proximo_pago") or Decimal("0.00")
            )
            fecha_referencia = (
                cuota_referencia.fecha_pago_debito
                if cuota_referencia
                else self.cleaned_data.get("fecha_proximo_pago")
            )
            if valor_referencia <= 0:
                raise forms.ValidationError("No se encontró un valor válido para generar las nuevas cuotas.")
            if not fecha_referencia:
                raise forms.ValidationError("Ingresa la fecha de la primera cuota antes de agregar cuotas.")
        return value

    def clean(self):
        data = super().clean()
        if data.get("valor_matricula") != self.initial.get("valor_matricula", Decimal("0.00")) and not self.payment_fields_locked:
            if not self.instance.pk or not PlanPago.objects.filter(ficha_inscripcion=self.instance, activo=True).exists():
                self.add_error("valor_matricula", "La ficha necesita un plan de pago activo para modificar la matrícula.")
        return data

    @transaction.atomic
    def save(self, commit=True):
        plan = None
        cuotas = []
        valor_matricula_inicial = self.initial.get("valor_matricula", Decimal("0.00"))
        matricula_changed = self.cleaned_data["valor_matricula"] != valor_matricula_inicial
        schedule_changed = (
            self.cleaned_data.get("fecha_proximo_pago") != self.initial.get("fecha_proximo_pago")
            or self.cleaned_data.get("forma_pago_convenio") != self.initial.get("forma_pago_convenio")
        )
        numero_cuotas = self.cleaned_data.get("numero_cuotas")
        installments_changed = (
            numero_cuotas is not None
            and numero_cuotas != self.current_installment_count
        )
        update_matricula = False
        if commit and self.instance.pk and not self.payment_fields_locked:
            plan = PlanPago.objects.select_for_update().filter(ficha_inscripcion=self.instance, activo=True).first()
            if plan:
                missing = self.cleaned_data["valor_matricula"] > 0 and not plan.cuotas.filter(
                    numero=Cuota.NUMERO_MATRICULA, activo=True,
                ).exists()
                update_matricula = matricula_changed or missing
                if not update_matricula and not schedule_changed and not installments_changed:
                    plan = None
            if plan:
                cuotas = list(plan.cuotas.select_for_update())
                if (update_matricula or schedule_changed) and plan.cuotas.filter(pagos__isnull=False).exists():
                    raise forms.ValidationError("Se registraron pagos mientras editabas. Recarga la ficha antes de guardar.")
        elif commit and self.instance.pk and installments_changed:
            plan = PlanPago.objects.select_for_update().filter(ficha_inscripcion=self.instance, activo=True).first()
            if plan:
                cuotas = list(plan.cuotas.select_for_update())
        ficha = super().save(commit=commit)
        if plan and update_matricula:
            valor = ficha.valor_matricula
            cuota = plan.cuotas.filter(numero=Cuota.NUMERO_MATRICULA).first()
            if valor > 0 or cuota:
                Cuota.objects.update_or_create(
                    plan_pago=plan, numero=Cuota.NUMERO_MATRICULA,
                    defaults={"valor": valor, "valor_pagado": Decimal("0.00"),
                              "fecha_pago_debito": cuota.fecha_pago_debito if cuota else ficha.fecha,
                              "estado": "pendiente" if valor > 0 else "anulada",
                              "activo": valor > 0, "observacion": "Matricula"},
                )
            diferencia = valor - plan.valor_matricula
            plan.valor_matricula = valor
            plan.valor_total += diferencia
            plan.saldo += diferencia
            if plan.saldo > 0 and plan.estado == "cerrado":
                plan.estado = "activo"
            plan.save(update_fields=["valor_matricula", "valor_total", "saldo", "estado", "updated"])
            ficha.saldo = plan.saldo
            ficha.save(update_fields=["saldo"])
        if plan and installments_changed:
            self.update_installments(plan, ficha, numero_cuotas, cuotas)
        if plan and schedule_changed and ficha.fecha_proximo_pago:
            for cuota in plan.cuotas.filter(numero__gt=0, activo=True):
                if cuota.numero <= 0:
                    continue
                cuota.fecha_pago_debito = fecha_cuota(
                    ficha.fecha_proximo_pago,
                    ficha.forma_pago_convenio,
                    cuota.numero,
                )
                if cuota.estado not in {"pagada", "anulada"}:
                    cuota.estado = "parcial" if cuota.valor_pagado > 0 else "pendiente"
                cuota.save(update_fields=["fecha_pago_debito", "estado", "updated"])
        estudiante = self.cleaned_data.get("estudiante")
        if commit and estudiante:
            estudiante.es_de_ibarra = self.cleaned_data.get("estudiante_es_de_ibarra", False)
            estudiante.save(update_fields=["es_de_ibarra"])
        return ficha

    def update_installments(self, plan, ficha, numero_cuotas, locked_installments):
        cuotas_por_numero = {
            cuota.numero: cuota
            for cuota in locked_installments
            if cuota.numero > 0
        }
        cuota_referencia = next(
            (cuotas_por_numero[numero] for numero in sorted(cuotas_por_numero)),
            None,
        )
        valor_cuota = (
            cuota_referencia.valor
            if cuota_referencia
            else self.cleaned_data.get("valor_proximo_pago") or Decimal("0.00")
        )
        fecha_primera_cuota = (
            cuota_referencia.fecha_pago_debito
            if cuota_referencia
            else ficha.fecha_proximo_pago
        )
        usuario = getattr(ficha, "usuario_updated", None)

        for numero in range(1, numero_cuotas + 1):
            cuota = cuotas_por_numero.get(numero)
            fecha = fecha_cuota(fecha_primera_cuota, ficha.forma_pago_convenio, numero)
            if cuota:
                if not cuota.activo or cuota.estado == "anulada":
                    cuota.activo = True
                    cuota.fecha_pago_debito = fecha
                    if cuota.valor <= 0:
                        cuota.valor = valor_cuota
                    cuota.estado = "pagada" if cuota.valor_pagado >= cuota.valor else (
                        "parcial" if cuota.valor_pagado > 0 else "pendiente"
                    )
                    cuota.usuario_updated = usuario
                    cuota.save(
                        update_fields=[
                            "activo",
                            "fecha_pago_debito",
                            "valor",
                            "estado",
                            "usuario_updated",
                            "updated",
                        ]
                    )
                continue
            Cuota.objects.create(
                plan_pago=plan,
                numero=numero,
                fecha_pago_debito=fecha,
                valor=valor_cuota,
                valor_pagado=Decimal("0.00"),
                estado="pendiente",
                prioridad="normal",
                activo=True,
                usuario_updated=usuario,
            )

        cuotas_a_retirar = plan.cuotas.filter(numero__gt=numero_cuotas, activo=True)
        if cuotas_a_retirar.filter(Q(pagos__isnull=False) | Q(valor_pagado__gt=0)).exists():
            raise forms.ValidationError(
                "Se registraron pagos en una cuota que intentabas retirar. Recarga la ficha antes de guardar."
            )
        cuotas_a_retirar.update(
            activo=False,
            estado="anulada",
            usuario_updated=usuario,
            updated=timezone.now(),
        )

        valor_total_curso = sum(
            plan.cuotas.filter(numero__gt=0, activo=True).values_list("valor", flat=True),
            Decimal("0.00"),
        )
        plan.valor_total = plan.valor_matricula + valor_total_curso
        plan.saldo = max(plan.valor_total - plan.descuento - plan.abono, Decimal("0.00"))
        if plan.saldo == 0 and plan.estado != "anulado":
            plan.estado = "cerrado"
        elif plan.saldo > 0 and plan.estado == "cerrado":
            plan.estado = "activo"
        plan.usuario_updated = usuario
        plan.save(update_fields=["valor_total", "saldo", "estado", "usuario_updated", "updated"])

        ficha.valor_total_curso = valor_total_curso
        ficha.saldo = plan.saldo
        ficha.save(update_fields=["valor_total_curso", "saldo", "updated"])


class MatriculaProcesoForm(BootstrapFormMixin, forms.Form):
    FORMAS_PAGO_CONVENIO = FichaInscripcion.FORMA_PAGO_CONVENIO_CHOICES
    MODO_CHOICES = (
        ("seleccionar", "Seleccionar existente"),
        ("crear", "Crear nuevo"),
    )
    REPRESENTANTE_MODO_CHOICES = MODO_CHOICES + (
        ("autorepresentar", "El estudiante se representa a sí mismo"),
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
    estudiante_nombre = forms.CharField(label="Nombres estudiante", max_length=200, required=False)
    estudiante_apellido = forms.CharField(label="Apellidos estudiante", max_length=200, required=False)
    estudiante_fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento estudiante",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    estudiante_email = forms.EmailField(label="Correo estudiante", required=False)
    estudiante_telefono = forms.CharField(label="Celular estudiante", max_length=50, required=False)
    colegio = forms.CharField(max_length=200, required=False)
    estudiante_es_de_ibarra = forms.BooleanField(
        label="Es de Ibarra",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "js-switch"}),
    )
    curso_grado = forms.CharField(label="Curso/Grado", max_length=120, required=False)

    representante_modo = forms.ChoiceField(
        label="Registro del representante",
        choices=REPRESENTANTE_MODO_CHOICES,
        initial="seleccionar",
        widget=forms.RadioSelect(attrs={"class": "mode-options"}),
    )
    representante_partner = forms.ModelChoiceField(
        label="Seleccionar representante",
        queryset=Partner.objects.none(),
        required=False,
    )
    representante_identificacion = forms.CharField(label="R.U.C./C.I. representante", max_length=20, required=False)
    representante_nombre = forms.CharField(label="Nombres representante", max_length=200, required=False)
    representante_apellido = forms.CharField(label="Apellidos representante", max_length=200, required=False)
    representante_telefono = forms.CharField(label="Telefono representante", max_length=50, required=False)
    representante_celular = forms.CharField(label="Celular representante", max_length=50, required=False)
    representante_email = forms.EmailField(label="Correo representante", required=False)
    representante_ocupacion = forms.CharField(label="Ocupacion representante", max_length=100, required=False)
    representante_direccion = forms.CharField(label="Direccion", max_length=200, required=False)

    numero = forms.CharField(label="No. ficha", max_length=30, required=False)
    fecha = forms.DateField(label="Fecha", initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
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
        label="Forma de pago inicial",
        queryset=FormaPago.objects.none(),
        required=False,
    )
    numero_documento_abono = forms.CharField(label="No. recibo/factura/deposito inicial", max_length=60, required=False)
    numero_cuotas = forms.IntegerField(label="Numero de cuotas", min_value=1, initial=1)
    fecha_inicio_cobro = forms.DateField(
        label="Fecha primera cuota",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
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
        self.fields["fecha"].initial = timezone.localdate
        self.fields["fecha_inicio_cobro"].initial = timezone.localdate

        if not self.is_bound and not self.initial.get("estudiante_modo") and not estudiantes.exists():
            self.fields["estudiante_modo"].initial = "crear"
        if not self.is_bound and not self.initial.get("representante_modo") and not representantes.exists():
            self.fields["representante_modo"].initial = "crear"

        self.fields["periodo_academico"].widget.attrs["data-periodo-select"] = "true"
        self.fields["numero"].disabled = True
        self.fields["numero"].widget.attrs["readonly"] = "readonly"
        self.fields["numero"].widget.attrs["aria-readonly"] = "true"
        self.fields["fecha"].disabled = True
        self.fields["fecha"].widget.attrs["readonly"] = "readonly"
        self.fields["fecha"].widget.attrs["aria-readonly"] = "true"
        self.fields["curso"].widget.attrs["data-curso-select"] = "true"
        self.fields["aula"].widget.attrs["data-aula-select"] = "true"
        self.fields["horario"].widget.attrs["data-aula-horario"] = "horario"
        self.fields["hora"].widget.attrs["data-aula-horario"] = "hora"
        self.fields["duracion"].widget.attrs["data-aula-horario"] = "duracion"
        self.fields["valor_matricula"].widget.attrs["data-money-input"] = "matricula"
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
        valor_matricula = cleaned_data.get("valor_matricula") or 0
        abono = cleaned_data.get("abono") or 0
        total_cuotas = valor_cuota * numero_cuotas
        total = total_cuotas + valor_matricula
        saldo = total - abono
        if saldo < 0:
            self.add_error("abono", "El abono no puede ser mayor que la matricula mas las cuotas.")
        cleaned_data["saldo_calculado"] = saldo
        cleaned_data["valor_total_curso"] = total_cuotas
        cleaned_data["descuento"] = Decimal("0.00")
        if abono > 0 and not cleaned_data.get("forma_pago_abono"):
            self.add_error("forma_pago_abono", "Seleccione la forma de pago inicial.")
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
            cleaned_data["estudiante_apellido"] = partner.apellido
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
        if not cleaned_data.get("estudiante_apellido"):
            self.add_error("estudiante_apellido", "Ingrese el apellido del estudiante.")

    def clean_representante(self, cleaned_data):
        if "representante_modo" not in self.fields:
            return
        modo = cleaned_data.get("representante_modo")
        partner = cleaned_data.get("representante_partner")
        if modo == "autorepresentar":
            estudiante = Partner.objects.filter(
                pk=self.estudiante_guardado_id,
                es_estudiante=True,
                activo=True,
            ).first()
            if not estudiante:
                self.add_error(None, "Primero guarde un estudiante activo para usar la autorrepresentación.")
                return
            edad = calcular_edad(estudiante.fecha_nacimiento)
            if edad is None:
                self.add_error(None, "El estudiante debe tener una fecha de nacimiento para autorrepresentarse.")
                return
            if edad < 18:
                self.add_error(None, "Solo un estudiante mayor de edad puede representarse a sí mismo.")
                return
            cleaned_data["representante_partner"] = estudiante
            cleaned_data["representante_identificacion"] = estudiante.identificacion
            cleaned_data["representante_nombre"] = estudiante.nombre
            cleaned_data["representante_apellido"] = estudiante.apellido
            cleaned_data["representante_email"] = estudiante.email
            cleaned_data["representante_telefono"] = estudiante.telefono
            cleaned_data["representante_celular"] = estudiante.telefono_celular
            cleaned_data["representante_ocupacion"] = estudiante.ocupacion
            cleaned_data["representante_direccion"] = estudiante.direccion
            return
        if modo == "seleccionar":
            if not partner:
                self.add_error("representante_partner", "Seleccione un representante activo.")
                return
            conyuge = representante_conyuge_data(partner)
            cleaned_data["representante_identificacion"] = partner.identificacion
            cleaned_data["representante_nombre"] = partner.nombre
            cleaned_data["representante_apellido"] = partner.apellido
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
        if not cleaned_data.get("representante_apellido"):
            self.add_error("representante_apellido", "Ingrese el apellido del representante.")

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
        if cleaned_data.get("representante_modo") == "autorepresentar":
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
        "estudiante_apellido",
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
        "representante_apellido",
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
        "estudiante_es_de_ibarra",
        "curso_grado",
        "nota_grado",
        "carrera",
        "universidad",
    )


class MatriculaConvenioForm(MatriculaPasoForm):
    field_names = (
        "forma_pago_convenio",
        "valor_matricula",
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
