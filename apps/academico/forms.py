from django import forms
from django.forms import formset_factory

from apps.core.forms import BootstrapFormMixin

from apps.core.models import Partner

from apps.matricula.models import Aula as MatriculaAula, PeriodoAcademico

from .models import Asignatura, Aula, BancoPregunta, Curso, Dia, HorarioClase, Materia, PlanificacionClase, Pregunta, Tema, Temario


class HorarioAsignacionBaseForm(BootstrapFormMixin, forms.Form):
    periodo_academico = forms.ModelChoiceField(label="Periodo", queryset=PeriodoAcademico.objects.none())
    aula = forms.ModelChoiceField(queryset=MatriculaAula.objects.none())
    asignatura = forms.ModelChoiceField(queryset=Asignatura.objects.none())
    docente = forms.ModelChoiceField(queryset=Partner.objects.none())
    tutor = forms.ModelChoiceField(queryset=Partner.objects.none(), required=False)
    fecha_inicio = forms.DateField(label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    fecha_fin = forms.DateField(label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    hora_inicio = forms.TimeField(label="Inicio", widget=forms.TimeInput(attrs={"type": "text", "class": "form-control js-time-picker"}))
    hora_fin = forms.TimeField(label="Fin", widget=forms.TimeInput(attrs={"type": "text", "class": "form-control js-time-picker"}))
    dias_semana = forms.MultipleChoiceField(
        label="Dias",
        choices=(
            ("0", "Lun"),
            ("1", "Mar"),
            ("2", "Mie"),
            ("3", "Jue"),
            ("4", "Vie"),
            ("5", "Sab"),
            ("6", "Dom"),
        ),
        widget=forms.CheckboxSelectMultiple,
    )
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        docentes = Partner.objects.filter(es_docente=True, activo=True).order_by("nombre")
        asignaturas = Asignatura.objects.filter(activo=True).order_by("nombre")
        if empresa:
            self.fields["periodo_academico"].queryset = PeriodoAcademico.objects.filter(empresa=empresa, activo=True)
            self.fields["aula"].queryset = MatriculaAula.objects.filter(empresa=empresa, activo=True)
            docentes = docentes.filter(empresa=empresa)
            asignaturas = asignaturas.filter(empresa=empresa)
        else:
            self.fields["periodo_academico"].queryset = PeriodoAcademico.objects.filter(activo=True)
            self.fields["aula"].queryset = MatriculaAula.objects.filter(activo=True)
        self.fields["asignatura"].queryset = asignaturas
        self.fields["docente"].queryset = docentes
        self.fields["tutor"].queryset = docentes

    def clean(self):
        cleaned_data = super().clean()
        periodo = cleaned_data.get("periodo_academico")
        fecha_inicio = cleaned_data.get("fecha_inicio")
        fecha_fin = cleaned_data.get("fecha_fin")
        hora_inicio = cleaned_data.get("hora_inicio")
        hora_fin = cleaned_data.get("hora_fin")
        if periodo and periodo.fecha_inicio and not fecha_inicio:
            cleaned_data["fecha_inicio"] = periodo.fecha_inicio
            fecha_inicio = periodo.fecha_inicio
        if periodo and periodo.fecha_fin and not fecha_fin:
            cleaned_data["fecha_fin"] = periodo.fecha_fin
            fecha_fin = periodo.fecha_fin
        if not fecha_inicio:
            self.add_error("fecha_inicio", "Define la fecha desde o configura el inicio del periodo.")
        if not fecha_fin:
            self.add_error("fecha_fin", "Define la fecha hasta o configura el fin del periodo.")
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            self.add_error("fecha_fin", "La fecha hasta debe ser mayor o igual que desde.")
        if periodo and periodo.fecha_inicio and fecha_inicio and fecha_inicio < periodo.fecha_inicio:
            self.add_error("fecha_inicio", "La fecha desde no puede estar antes del inicio del periodo.")
        if periodo and periodo.fecha_fin and fecha_fin and fecha_fin > periodo.fecha_fin:
            self.add_error("fecha_fin", "La fecha hasta no puede pasar del fin del periodo.")
        if hora_inicio and hora_fin and hora_inicio >= hora_fin:
            self.add_error("hora_fin", "La hora fin debe ser mayor que la hora inicio.")
        return cleaned_data


class HorarioAsignacionItemForm(BootstrapFormMixin, forms.Form):
    fecha = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    hora_inicio = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "text", "class": "form-control js-time-picker"}))
    hora_fin = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "text", "class": "form-control js-time-picker"}))
    asignatura = forms.ModelChoiceField(queryset=Asignatura.objects.none(), required=False)
    docente = forms.ModelChoiceField(queryset=Partner.objects.none(), required=False)
    tutor = forms.ModelChoiceField(queryset=Partner.objects.none(), required=False)
    estado = forms.ChoiceField(choices=HorarioClase.ESTADO_CHOICES, initial="programada", required=False)

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        docentes = Partner.objects.filter(es_docente=True, activo=True).order_by("nombre")
        asignaturas = Asignatura.objects.filter(activo=True).order_by("nombre")
        if empresa:
            docentes = docentes.filter(empresa=empresa)
            asignaturas = asignaturas.filter(empresa=empresa)
        self.fields["asignatura"].queryset = asignaturas
        self.fields["docente"].queryset = docentes
        self.fields["tutor"].queryset = docentes

    def has_schedule_data(self):
        fields = ["fecha", "hora_inicio", "hora_fin", "asignatura", "docente"]
        return any(self.cleaned_data.get(field) for field in fields)

    def clean(self):
        cleaned_data = super().clean()
        if not self.has_schedule_data():
            return cleaned_data
        required_fields = ["fecha", "hora_inicio", "hora_fin", "asignatura", "docente"]
        for field in required_fields:
            if not cleaned_data.get(field):
                self.add_error(field, "Completa este campo.")
        return cleaned_data


HorarioAsignacionFormSet = formset_factory(HorarioAsignacionItemForm, extra=8, can_delete=False)


class AsignaturaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Asignatura
        fields = ["empresa", "codigo", "nombre", "activo"]


class CursoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Curso
        fields = ["nombre", "activo", "descripcion"]
        widgets = {
            "activo": forms.CheckboxInput(attrs={"class": "js-switch"}),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }


class AulaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Aula
        fields = ["nombre", "descripcion"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }


class MateriaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Materia
        fields = ["nombre", "nombre_corto", "descripcion"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }


class HorarioDistribucionBaseForm(BootstrapFormMixin, forms.Form):
    curso = forms.ModelChoiceField(
        label="Grupo",
        queryset=Curso.objects.none(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["curso"].queryset = Curso.objects.filter(activo=True).order_by("nombre")


class HorarioDistribucionItemForm(BootstrapFormMixin, forms.Form):
    aula = forms.ModelChoiceField(queryset=Aula.objects.none(), required=False)
    dia = forms.ModelChoiceField(queryset=Dia.objects.none(), required=False)
    hora_inicio = forms.TimeField(
        label="Hora inicio",
        required=False,
        widget=forms.TimeInput(attrs={"type": "text", "class": "form-control js-time-picker"}),
    )
    hora_fin = forms.TimeField(
        label="Hora fin",
        required=False,
        widget=forms.TimeInput(attrs={"type": "text", "class": "form-control js-time-picker"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["aula"].queryset = Aula.objects.order_by("nombre")
        self.fields["dia"].queryset = Dia.objects.order_by("id")

    def has_schedule_data(self):
        return any(
            self.cleaned_data.get(field)
            for field in ["aula", "dia", "hora_inicio", "hora_fin"]
        )

    def clean(self):
        cleaned_data = super().clean()
        if not self.has_schedule_data():
            return cleaned_data

        for field in ["aula", "dia", "hora_inicio", "hora_fin"]:
            if not cleaned_data.get(field):
                self.add_error(field, "Completa este campo.")

        hora_inicio = cleaned_data.get("hora_inicio")
        hora_fin = cleaned_data.get("hora_fin")
        if hora_inicio and hora_fin and hora_fin <= hora_inicio:
            self.add_error("hora_fin", "La hora fin debe ser mayor que la hora inicio.")
        return cleaned_data


HorarioDistribucionFormSet = formset_factory(
    HorarioDistribucionItemForm,
    extra=0,
    can_delete=False,
)


class TemarioForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Temario
        fields = ["empresa", "periodo_academico", "asignatura", "nombre", "estado", "activo"]


class HorarioClaseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = HorarioClase
        fields = [
            "empresa",
            "periodo_academico",
            "aula",
            "fecha",
            "hora_inicio",
            "hora_fin",
            "asignatura",
            "docente",
            "tutor",
            "estado",
            "activo",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "text", "class": "form-control js-time-picker"}),
            "hora_fin": forms.TimeInput(attrs={"type": "text", "class": "form-control js-time-picker"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        docentes = Partner.objects.filter(es_docente=True, activo=True).order_by("nombre")
        self.fields["docente"].queryset = docentes
        self.fields["tutor"].queryset = docentes

    def clean(self):
        cleaned_data = super().clean()
        instance = self.instance
        for field, value in cleaned_data.items():
            setattr(instance, field, value)
        instance.clean()
        return cleaned_data


class TemaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Tema
        fields = [
            "temario",
            "nombre",
            "orden",
            "objetivo",
            "numero_clases",
            "dificultad",
            "meta_preguntas_proceso",
            "meta_preguntas_final",
            "activo",
        ]
        widgets = {"objetivo": forms.Textarea(attrs={"rows": 3})}


class PlanificacionClaseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PlanificacionClase
        fields = [
            "tema",
            "subtema",
            "numero_clase",
            "objetivo",
            "competencias",
            "estrategias",
            "actividades",
            "recursos_previstos",
        ]
        widgets = {
            "objetivo": forms.Textarea(attrs={"rows": 3}),
            "competencias": forms.Textarea(attrs={"rows": 4}),
            "estrategias": forms.Textarea(attrs={"rows": 5}),
            "actividades": forms.Textarea(attrs={"rows": 4}),
            "recursos_previstos": forms.Textarea(attrs={"rows": 3}),
        }


class BancoPreguntaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BancoPregunta
        fields = [
            "empresa",
            "asignatura",
            "tema",
            "subtema",
            "tipo",
            "meta_preguntas",
            "revisado_coordinacion",
            "activo",
        ]


class PreguntaForm(BootstrapFormMixin, forms.ModelForm):
    respuestas_texto = forms.CharField(
        label="Respuestas",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Una respuesta por linea"}),
    )

    class Meta:
        model = Pregunta
        fields = [
            "banco_pregunta",
            "creado_por",
            "enunciado",
            "respuestas_texto",
            "respuesta_correcta",
            "explicacion",
            "dificultad",
            "estado",
        ]
        widgets = {
            "enunciado": forms.Textarea(attrs={"rows": 4}),
            "respuesta_correcta": forms.Textarea(attrs={"rows": 2}),
            "explicacion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["respuestas_texto"].initial = "\n".join(self.instance.respuestas or [])

    def save(self, commit=True):
        instance = super().save(commit=False)
        respuestas = self.cleaned_data.get("respuestas_texto") or ""
        instance.respuestas = [line.strip() for line in respuestas.splitlines() if line.strip()]
        if commit:
            instance.save()
            self.save_m2m()
        return instance
