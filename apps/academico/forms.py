from decimal import Decimal

from django import forms
from django.db.models import Exists, OuterRef, Q
from django.forms import BaseFormSet, formset_factory
from django.utils import timezone

from apps.core.forms import BootstrapFormMixin

from apps.core.models import Partner

from apps.matricula.models import Aula as MatriculaAula, FichaInscripcion, PeriodoAcademico

from .durations import minutes_to_duration, split_duration
from .models import (
    Asignatura,
    Aula,
    BancoPregunta,
    Clase,
    ClaseHoraDocente,
    Competencia,
    Curso,
    CursoPeriodo,
    Dia,
    Estrategia,
    GrupoEstudiante,
    HorarioClase,
    Materia,
    MateriaCurso,
    MoodleConfiguracion,
    Periodo,
    PlanificacionClase,
    PlanificacionDocente,
    ProfesorMateriaCurso,
    Pregunta,
    Recurso,
    Subtema,
    Tema,
    Temario,
)


class MoodleConfiguracionForm(BootstrapFormMixin, forms.ModelForm):
    token = forms.CharField(
        label="Token del servicio web",
        required=False,
        help_text="Por seguridad, el token guardado no se vuelve a mostrar. Déjalo vacío para conservarlo.",
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password", "placeholder": "Pega aquí el token de Moodle"},
        ),
    )
    clave_inicial = forms.CharField(
        label="Clave inicial para cuentas nuevas",
        required=False,
        min_length=8,
        help_text=(
            "Se asigna solo a cuentas nuevas y Moodle solicitará cambiarla al ingresar. "
            "Déjala vacía para conservar la configuración actual."
        ),
        widget=forms.PasswordInput(
            render_value=False,
            attrs={
                "autocomplete": "new-password",
                "placeholder": "Mínimo 8 caracteres; usa letras, números y símbolos",
            },
        ),
    )

    class Meta:
        model = MoodleConfiguracion
        fields = ["base_url"]
        widgets = {
            "base_url": forms.TextInput(
                attrs={"placeholder": "https://aula.solucionesintegrales.xyz", "autocomplete": "url"}
            ),
        }

    def clean_base_url(self):
        from .moodle import MoodleError, normalize_moodle_url

        try:
            return normalize_moodle_url(self.cleaned_data["base_url"])
        except MoodleError as exc:
            raise forms.ValidationError(str(exc)) from None

    def clean_token(self):
        token = (self.cleaned_data.get("token") or "").strip()
        if not token and not self.instance.token_cifrado:
            raise forms.ValidationError("Ingresa el token del servicio web de Moodle.")
        return token

    def clean_clave_inicial(self):
        from django.conf import settings

        password = self.cleaned_data.get("clave_inicial") or ""
        if not password and not self.instance.clave_inicial_cifrada and not settings.MOODLE_INITIAL_PASSWORD:
            raise forms.ValidationError("Ingresa la clave inicial que recibirán las cuentas nuevas.")
        return password

    def save(self, commit=True):
        from .moodle import encrypt_moodle_token
        from .moodle_accounts import encrypt_configured_initial_password

        instance = super().save(commit=False)
        token = self.cleaned_data.get("token")
        password = self.cleaned_data.get("clave_inicial")
        if token:
            instance.token_cifrado = encrypt_moodle_token(token)
        if password:
            instance.clave_inicial_cifrada = encrypt_configured_initial_password(password)
        if commit:
            instance.save()
        return instance


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
    periodo = forms.ModelChoiceField(label="Periodo", queryset=Periodo.objects.none())

    class Meta:
        model = Curso
        fields = ["nombre", "periodo", "activo", "descripcion"]
        widgets = {
            "activo": forms.CheckboxInput(attrs={"class": "js-switch"}),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["periodo"].queryset = Periodo.objects.filter(estado="activo").order_by(
            "-fecha_inicio", "nombre"
        )
        if self.instance.pk:
            curso_periodo = self.instance.curso_periodos.select_related("periodo").order_by("-periodo__fecha_inicio").first()
            if curso_periodo:
                self.fields["periodo"].initial = curso_periodo.periodo
                self.fields["periodo"].queryset = Periodo.objects.filter(pk=curso_periodo.periodo_id)
                self.fields["periodo"].disabled = True
                self.fields["periodo"].help_text = (
                    "El periodo de un grupo existente no se cambia para proteger su historial. "
                    "Crea un grupo nuevo para el siguiente periodo."
                )

    def save(self, commit=True):
        curso = super().save(commit=commit)
        if commit:
            CursoPeriodo.objects.get_or_create(curso=curso, periodo=self.cleaned_data["periodo"])
        return curso


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
        fields = ["nombre", "nombre_corto", "color", "descripcion"]
        widgets = {
            "color": forms.TextInput(
                attrs={
                    "type": "text",
                    "autocomplete": "off",
                    "maxlength": "7",
                    "pattern": "^#[0-9A-Fa-f]{6}$",
                    "data-color-input": "",
                }
            ),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_color(self):
        color = (self.cleaned_data.get("color") or "").strip()
        if not color:
            return "#2563eb"
        if not color.startswith("#"):
            color = f"#{color}"
        if len(color) != 7:
            raise forms.ValidationError("Ingresa un color valido.")
        try:
            int(color[1:], 16)
        except ValueError as exc:
            raise forms.ValidationError("Ingresa un color valido.") from exc
        return color.lower()


class PeriodoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Periodo
        fields = ["nombre", "fecha_inicio", "fecha_fin"]
        widgets = {
            "fecha_inicio": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "text", "autocomplete": "off", "placeholder": "dd/mm/aaaa"},
            ),
            "fecha_fin": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "text", "autocomplete": "off", "placeholder": "dd/mm/aaaa"},
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        instance = self.instance
        for field, value in cleaned_data.items():
            setattr(instance, field, value)
        instance.clean()
        return cleaned_data


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


class PlanificacionDocenteBaseForm(BootstrapFormMixin, forms.Form):
    docente = forms.ModelChoiceField(queryset=Partner.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["docente"].queryset = Partner.objects.filter(es_docente=True, activo=True).order_by("nombre")


class PlanificacionDocenteItemForm(BootstrapFormMixin, forms.Form):
    grupo = forms.ModelChoiceField(queryset=Curso.objects.none(), required=False)
    materia_curso = forms.ModelChoiceField(label="Materia", queryset=MateriaCurso.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        self.docente = kwargs.pop("docente", None)
        super().__init__(*args, **kwargs)
        self.fields["grupo"].queryset = Curso.objects.filter(activo=True).order_by("nombre")
        self.fields["materia_curso"].queryset = MateriaCurso.objects.select_related("materia", "grupo").order_by("grupo__nombre", "materia__nombre")
        self.fields["materia_curso"].label_from_instance = lambda obj: obj.materia.nombre

    def has_assignment_data(self):
        return any(self.cleaned_data.get(field) for field in ["grupo", "materia_curso"])

    def clean(self):
        cleaned_data = super().clean()
        if self.cleaned_data.get("DELETE"):
            return cleaned_data
        if not self.has_assignment_data():
            return cleaned_data

        grupo = cleaned_data.get("grupo")
        materia_curso = cleaned_data.get("materia_curso")
        if not grupo:
            self.add_error("grupo", "Selecciona un grupo.")
        if not materia_curso:
            self.add_error("materia_curso", "Selecciona una materia.")
        if grupo and materia_curso and materia_curso.grupo_id != grupo.pk:
            self.add_error("materia_curso", "La materia no pertenece al grupo seleccionado.")
        if materia_curso:
            assigned = ProfesorMateriaCurso.objects.select_related("partner").filter(
                materia_curso=materia_curso,
                auto_generada_por_clases=False,
            )
            if self.docente:
                assigned = assigned.exclude(partner=self.docente)
            existing = assigned.first()
            if existing:
                self.add_error(
                    "materia_curso",
                    f"Esta materia del grupo ya esta asignada a {existing.partner}.",
                )
        return cleaned_data


PlanificacionDocenteFormSet = formset_factory(
    PlanificacionDocenteItemForm,
    extra=0,
    can_delete=True,
)


class GrupoEstudianteBulkForm(BootstrapFormMixin, forms.Form):
    grupo = forms.ModelChoiceField(label="Grupo", queryset=Curso.objects.none())
    fichas = forms.ModelMultipleChoiceField(
        label="Estudiantes sin grupo",
        queryset=FichaInscripcion.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    fecha_asignacion = forms.DateField(
        label="Fecha de asignacion",
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
    )

    def __init__(self, *args, **kwargs):
        selected_group = kwargs.pop("selected_group", None)
        super().__init__(*args, **kwargs)
        self.selected_period = self.get_group_period(selected_group)
        self.fields["grupo"].queryset = (
            Curso.objects.filter(activo=True)
            .filter(Q(curso_periodos__periodo__estado="activo") | Q(curso_periodos__isnull=True))
            .distinct()
            .order_by("nombre")
        )
        if selected_group and not self.fields["grupo"].queryset.filter(pk=selected_group.pk).exists():
            self.fields["grupo"].queryset = Curso.objects.filter(
                Q(pk=selected_group.pk) | Q(curso_periodos__periodo__estado="activo") | Q(curso_periodos__isnull=True),
                activo=True,
            ).distinct().order_by("nombre")

        fichas = (
            FichaInscripcion.objects.select_related("estudiante")
            .filter(estudiante__es_estudiante=True, estudiante__activo=True, activo=True)
            .exclude(estado="anulada")
        )
        if self.selected_period:
            occupied_in_period = GrupoEstudiante.objects.filter(
                ficha_inscripcion_id=OuterRef("pk"),
                periodo=self.selected_period,
                estado__in=("activo", "finalizado"),
            )
            fichas = fichas.annotate(occupied_in_period=Exists(occupied_in_period)).filter(
                occupied_in_period=False
            )
            if self.selected_period.estado == "cerrado":
                fichas = fichas.none()
            elif not self.is_bound:
                self.fields["fecha_asignacion"].initial = max(
                    timezone.localdate(), self.selected_period.fecha_inicio
                )
        else:
            occupied = GrupoEstudiante.objects.filter(
                ficha_inscripcion_id=OuterRef("pk"),
                estado="activo",
            )
            fichas = fichas.annotate(occupied=Exists(occupied)).filter(occupied=False)
        self.fields["fichas"].queryset = fichas.order_by(
            "estudiante__apellido", "estudiante__nombre", "numero"
        )
        self.fields["fichas"].label_from_instance = (
            lambda ficha: f"{' '.join(filter(None, [ficha.estudiante.apellido, ficha.estudiante.nombre]))} - ficha {ficha.numero}"
        )
        if selected_group:
            self.fields["grupo"].initial = selected_group

    @staticmethod
    def get_group_period(group):
        if not group:
            return None
        link = group.curso_periodos.select_related("periodo").order_by(
            "-periodo__fecha_inicio", "-pk"
        ).first()
        return link.periodo if link else None

    def clean(self):
        cleaned_data = super().clean()
        group = cleaned_data.get("grupo")
        period = self.get_group_period(group)
        self.selected_period = period
        if period and period.estado != "activo":
            self.add_error("grupo", "El periodo de este grupo ya esta cerrado.")
        assignment_date = cleaned_data.get("fecha_asignacion")
        if period and assignment_date:
            if assignment_date < period.fecha_inicio or assignment_date > period.fecha_fin:
                self.add_error(
                    "fecha_asignacion",
                    "La fecha de asignacion debe estar dentro del periodo del grupo.",
                )
        return cleaned_data


class ClaseEstudianteMovimientoForm(BootstrapFormMixin, forms.Form):
    asignacion = forms.ModelChoiceField(label="Estudiante", queryset=GrupoEstudiante.objects.none())
    materia_origen = forms.ModelChoiceField(label="Materia en grupo base", queryset=MateriaCurso.objects.none())
    materia_destino = forms.ModelChoiceField(label="Tomar esa materia en", queryset=MateriaCurso.objects.none())
    fecha_inicio = forms.DateField(
        label="Desde fecha",
        initial=timezone.localdate,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "text"}),
    )
    motivo = forms.CharField(label="Motivo", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        self.grupo = kwargs.pop("grupo", None)
        super().__init__(*args, **kwargs)
        asignaciones = GrupoEstudiante.objects.select_related("estudiante", "grupo").filter(
            estado="activo",
            estudiante__activo=True,
        )
        materias_origen = MateriaCurso.objects.select_related("materia", "grupo").filter(
            clases__isnull=False,
        )
        materias_destino = MateriaCurso.objects.select_related("materia", "grupo").filter(
            clases__isnull=False,
        )
        if self.grupo:
            asignaciones = asignaciones.filter(grupo=self.grupo)
            materias_origen = materias_origen.filter(grupo=self.grupo)
            materias_destino = materias_destino.exclude(grupo=self.grupo).filter(
                materia_id__in=materias_origen.values_list("materia_id", flat=True),
            )
        else:
            materias_destino = materias_destino.none()

        origin_id = self.data.get(self.add_prefix("materia_origen")) if self.is_bound else None
        origin = MateriaCurso.objects.filter(pk=origin_id).first() if origin_id else None
        if origin:
            materias_destino = materias_destino.filter(materia=origin.materia).exclude(pk=origin.pk)

        self.fields["asignacion"].queryset = asignaciones.order_by("estudiante__apellido", "estudiante__nombre")
        self.fields["materia_origen"].queryset = materias_origen.distinct().order_by("materia__nombre", "grupo__nombre")
        self.fields["materia_destino"].queryset = materias_destino.distinct().order_by("grupo__nombre", "materia__nombre")
        self.fields["asignacion"].label_from_instance = (
            lambda obj: " ".join(filter(None, [obj.estudiante.apellido, obj.estudiante.nombre]))
        )
        self.fields["materia_origen"].label_from_instance = self.materia_curso_label
        self.fields["materia_destino"].label_from_instance = self.materia_curso_label

    @staticmethod
    def materia_curso_label(materia_curso):
        return f"{materia_curso.materia} - {materia_curso.grupo}"

    def clean(self):
        cleaned_data = super().clean()
        asignacion = cleaned_data.get("asignacion")
        materia_origen = cleaned_data.get("materia_origen")
        materia_destino = cleaned_data.get("materia_destino")
        fecha_inicio = cleaned_data.get("fecha_inicio")
        if not asignacion or not materia_origen or not materia_destino or not fecha_inicio:
            return cleaned_data

        if asignacion.grupo_id != materia_origen.grupo_id:
            self.add_error("materia_origen", "La materia origen debe pertenecer al grupo base del estudiante.")
            return cleaned_data
        if materia_origen.materia_id != materia_destino.materia_id:
            self.add_error("materia_destino", "Selecciona la misma materia en otro grupo.")
            return cleaned_data
        if materia_origen.pk == materia_destino.pk:
            self.add_error("materia_destino", "Selecciona otro grupo para esta materia.")
            return cleaned_data

        clase_origen = self.get_first_class(materia_origen, fecha_inicio)
        clase_destino = self.get_first_class(materia_destino, fecha_inicio)
        if not clase_origen:
            self.add_error("materia_origen", "No hay clases de esta materia desde la fecha indicada.")
        if not clase_destino:
            self.add_error("materia_destino", "El grupo destino no tiene clases de esta materia desde la fecha indicada.")
        if clase_origen and clase_destino:
            cleaned_data["clase_origen"] = clase_origen
            cleaned_data["clase_destino"] = clase_destino
        return cleaned_data

    @staticmethod
    def get_first_class(materia_curso, fecha_inicio):
        return (
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__horario",
            )
            .filter(materia_curso=materia_curso, fecha__gte=fecha_inicio)
            .order_by("fecha", "horario_aula_curso__horario_dia__horario__hora_inicio")
            .first()
        )


class CoordinacionPlanificacionForm(BootstrapFormMixin, forms.Form):
    materia = forms.ModelChoiceField(
        label="Materia",
        queryset=Materia.objects.none(),
    )

    def __init__(self, *args, **kwargs):
        materia = kwargs.pop("materia", None)
        materia_curso = kwargs.pop("materia_curso", None)
        materias = kwargs.pop("materias", None)
        super().__init__(*args, **kwargs)
        self.fields["materia"].queryset = materias if materias is not None else Materia.objects.order_by("nombre")
        if materia_curso:
            self.fields["materia"].initial = materia_curso.materia
            self.fields["materia"].disabled = True
        elif materia:
            self.fields["materia"].initial = materia
            self.fields["materia"].disabled = True


class CoordinacionTemaForm(BootstrapFormMixin, forms.Form):
    tema_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    nombre = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"data-topic-name": "", "placeholder": "Ej. Operaciones algebraicas"}),
    )
    detalle = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Breve alcance del tema"}),
    )
    orden = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)

    def has_topic_data(self):
        return any(
            self.cleaned_data.get(field)
            for field in ["tema_id", "nombre", "detalle", "orden"]
        )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE") or not self.has_topic_data():
            return cleaned_data
        if not cleaned_data.get("nombre"):
            self.add_error("nombre", "Escribe el nombre del tema.")
        if not cleaned_data.get("orden"):
            cleaned_data["orden"] = 1
        return cleaned_data


class BaseCoordinacionTemaFormSet(BaseFormSet):
    def clean(self):
        self.error_summary = []
        super().clean()
        if any(self.errors):
            return

        topics_by_name = {}
        for topic_index, topic_form in enumerate(self.forms, start=1):
            if topic_form.cleaned_data.get("DELETE") or not topic_form.has_topic_data():
                continue
            topic_name = topic_form.cleaned_data.get("nombre") or ""
            normalized_name = " ".join(topic_name.split()).casefold()
            if not normalized_name:
                continue
            topics_by_name.setdefault(normalized_name, []).append((topic_index, topic_form, topic_name.strip()))

        for repeated_topics in topics_by_name.values():
            if len(repeated_topics) < 2:
                continue
            positions = " y ".join(str(index) for index, _form, _name in repeated_topics)
            repeated_name = repeated_topics[0][2]
            message = (
                f'El tema "{repeated_name}" está repetido en las posiciones {positions}. '
                "Cada tema de la materia debe tener un nombre diferente."
            )
            self.error_summary.append(message)
            for _index, topic_form, _name in repeated_topics:
                topic_form.add_error("nombre", message)


CoordinacionTemaFormSet = formset_factory(
    CoordinacionTemaForm,
    formset=BaseCoordinacionTemaFormSet,
    extra=0,
    can_delete=True,
)


class DocenteClasePlanificacionForm(BootstrapFormMixin, forms.ModelForm):
    temas_seleccionados = forms.ModelMultipleChoiceField(
        label="Temas",
        queryset=Tema.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"data-topic-check": ""}),
    )
    subtemas_seleccionados = forms.ModelMultipleChoiceField(
        label="Subtemas",
        queryset=Subtema.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Clase
        fields = [
            "tema",
            "temas_seleccionados",
            "subtema",
            "subtemas_seleccionados",
            "descripcion",
        ]
        widgets = {
            "tema": forms.HiddenInput(),
            "subtema": forms.HiddenInput(),
            "descripcion": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        clase = kwargs.pop("clase", None)
        kwargs.pop("unavailable_subtema_ids", None)
        super().__init__(*args, **kwargs)
        clase = clase or self.instance
        temas = Tema.objects.none()
        subtemas = Subtema.objects.none()
        if clase and clase.pk:
            temas = Tema.objects.filter(planificacion__materia_curso=clase.materia_curso).order_by("orden", "nombre")
            subtemas = Subtema.objects.filter(tema__planificacion__materia_curso=clase.materia_curso).order_by("tema__orden", "orden", "nombre")
        self.fields["tema"].queryset = temas
        self.fields["temas_seleccionados"].queryset = temas
        self.fields["subtema"].queryset = subtemas
        self.fields["subtemas_seleccionados"].queryset = subtemas
        self.fields["tema"].required = False
        self.fields["subtema"].required = False
        if not self.is_bound and clase and clase.pk:
            self.fields["temas_seleccionados"].initial = [
                tema.pk for tema in clase.get_temas_planificados()
            ]
            selected_subtema_ids = [subtema.pk for subtema in clase.get_subtemas_planificados()]
            self.fields["subtemas_seleccionados"].initial = selected_subtema_ids

    def clean(self):
        cleaned_data = super().clean()
        tema = cleaned_data.get("tema")
        temas = list(cleaned_data.get("temas_seleccionados") or [])
        if tema and tema not in temas:
            temas.insert(0, tema)
        if temas:
            tema = temas[0]
            cleaned_data["tema"] = tema
        cleaned_data["temas_seleccionados"] = temas
        subtema = cleaned_data.get("subtema")
        subtemas = cleaned_data.get("subtemas_seleccionados") or []
        if subtema:
            if subtema not in subtemas:
                subtemas = list(subtemas)
                subtemas.insert(0, subtema)
                cleaned_data["subtemas_seleccionados"] = subtemas
        selected_tema_ids = {item.pk for item in temas}
        if subtemas and not temas:
            self.add_error("temas_seleccionados", "Selecciona al menos un tema de la clase.")
        for item in subtemas:
            if item.tema_id not in selected_tema_ids:
                self.add_error("subtemas_seleccionados", "Cada subtema debe pertenecer a uno de los temas seleccionados.")
                break
        return cleaned_data

    def save(self, commit=True):
        clase = super().save(commit=commit)
        if not commit:
            return clase
        clase.sync_temas_planificados(self.cleaned_data.get("temas_seleccionados") or [])
        selected_subtemas = list(self.cleaned_data.get("subtemas_seleccionados") or [])
        legacy_subtema = self.cleaned_data.get("subtema")
        if legacy_subtema and legacy_subtema not in selected_subtemas:
            selected_subtemas.insert(0, legacy_subtema)
        clase.sync_subtemas_planificados(selected_subtemas)
        return clase


class ClaseHoraDocenteForm(BootstrapFormMixin, forms.ModelForm):
    horas = forms.IntegerField(
        label="Horas",
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={"step": "1", "min": "0", "inputmode": "numeric"}),
    )
    minutos = forms.IntegerField(
        label="Minutos",
        min_value=0,
        max_value=59,
        initial=0,
        required=False,
        widget=forms.NumberInput(attrs={"step": "1", "min": "0", "max": "59", "inputmode": "numeric"}),
        error_messages={
            "min_value": "Los minutos deben estar entre 00 y 59.",
            "max_value": "Los minutos deben estar entre 00 y 59.",
            "invalid": "Ingresa los minutos como un número entre 00 y 59.",
        },
    )

    class Meta:
        model = ClaseHoraDocente
        fields = ["estado", "docente", "horas", "minutos", "observacion"]
        widgets = {
            "observacion": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {"docente": "Docente que dio clase"}

    def __init__(self, *args, **kwargs):
        self.clase = kwargs.pop("clase", None)
        self.docente_programado = kwargs.pop("docente_programado", None)
        super().__init__(*args, **kwargs)
        docentes = Partner.objects.filter(es_docente=True, activo=True).order_by("nombre", "apellido")
        self.fields["docente"].queryset = docentes
        self.fields["docente"].required = False
        self.fields["docente"].empty_label = "Sin docente"
        self.fields["estado"].widget.attrs["data-teacher-hour-state"] = ""
        self.fields["docente"].widget.attrs["data-teacher-hour-teacher"] = ""
        estado_value = self.current_estado_value()
        if estado_value != "reemplazo":
            self.fields["docente"].disabled = True
        if not self.is_bound:
            duration = self.initial.get("horas", getattr(self.instance, "horas", Decimal("0.00")))
            hours, minutes = split_duration(duration)
            self.initial["horas"] = hours
            self.initial["minutos"] = minutes

    def current_estado_value(self):
        if self.is_bound:
            return self.data.get(self.add_prefix("estado")) or "pendiente"
        return self.initial.get("estado") or getattr(self.instance, "estado", "") or "pendiente"

    def clean(self):
        cleaned_data = super().clean()
        estado = cleaned_data.get("estado")
        docente = cleaned_data.get("docente")
        hours = cleaned_data.get("horas") or 0
        minutes = cleaned_data.get("minutos") or 0
        horas = minutes_to_duration(hours * 60 + minutes)
        cleaned_data["horas"] = horas
        if estado == "asistio":
            cleaned_data["docente"] = self.docente_programado
            if not self.docente_programado:
                self.add_error("estado", "Esta clase no tiene docente programado. Usa reemplazo y selecciona el docente.")
            if horas <= 0:
                self.add_error("horas", "Ingresa las horas pagables.")
        if estado == "reemplazo":
            if not docente:
                self.add_error("docente", "Selecciona el docente que dio la clase.")
            if self.docente_programado and docente == self.docente_programado:
                self.add_error("docente", "El reemplazo debe ser distinto al docente programado.")
            if horas <= 0:
                self.add_error("horas", "Ingresa las horas pagables.")
        if estado in {"no_asistio", "suspendida", "pendiente"}:
            cleaned_data["horas"] = Decimal("0.00")
            if estado in {"no_asistio", "suspendida"}:
                cleaned_data["docente"] = None
        return cleaned_data


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
            "planificacion",
            "nombre",
            "detalle",
            "orden",
        ]
        widgets = {"detalle": forms.Textarea(attrs={"rows": 3})}


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
