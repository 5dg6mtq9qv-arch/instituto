from django import forms

from apps.core.forms import BootstrapFormMixin

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
