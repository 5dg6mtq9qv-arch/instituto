from django import forms

from apps.core.forms import BootstrapFormMixin

from apps.core.models import Partner

from .models import Asignatura, BancoPregunta, HorarioClase, PlanificacionClase, Pregunta, Tema, Temario


class AsignaturaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Asignatura
        fields = ["empresa", "codigo", "nombre", "activo"]


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
            "tipo_planificacion",
            "tema_previsto",
            "observacion",
            "estado",
            "activo",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}),
            "tema_previsto": forms.Textarea(attrs={"rows": 3}),
            "observacion": forms.Textarea(attrs={"rows": 3}),
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
            "empresa",
            "docente",
            "aula",
            "asignatura",
            "tema",
            "subtema",
            "numero_clase",
            "fecha_planificada",
            "objetivo",
            "actividades",
            "recursos_previstos",
            "estado",
        ]
        widgets = {
            "fecha_planificada": forms.DateInput(attrs={"type": "date"}),
            "objetivo": forms.Textarea(attrs={"rows": 3}),
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
