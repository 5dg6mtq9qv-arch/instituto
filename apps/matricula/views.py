from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.http import JsonResponse
from django.http import QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View

from apps.cartera.models import Cuota, FormaPago, Pago, PlanPago
from apps.core.models import Empresa, Partner, PartnerPartner, TipoIdentificacion
from apps.core.web_views import InstitutoCreateView, InstitutoListView, InstitutoUpdateView

from .forms import (
    AulaForm,
    CursoForm,
    FichaInscripcionForm,
    MatriculaConvenioForm,
    MatriculaDatosForm,
    MatriculaEstudianteForm,
    MatriculaProcesoForm,
    MatriculaRepresentanteForm,
    PeriodoAcademicoForm,
    representante_conyuge_data,
)
from .models import Aula, AulaHistorial, Curso, FichaInscripcion, PeriodoAcademico
from .odt import TEMPLATE_PATH, build_document_response_file


def add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def format_ficha_numero(sequence):
    return str(sequence).zfill(6)


def next_ficha_numero(empresa):
    siguiente = 1
    numeros = FichaInscripcion.objects.filter(empresa=empresa).values_list("numero", flat=True)
    for numero in numeros:
        numero = (numero or "").strip()
        if numero.isdigit():
            siguiente = max(siguiente, int(numero) + 1)
    return format_ficha_numero(siguiente)


class PeriodoAcademicoListView(InstitutoListView):
    model = PeriodoAcademico
    title = "Periodos academicos"
    create_url_name = "matricula:periodo_nuevo"
    columns = (("Nombre", "nombre"), ("Regimen", "regimen"), ("Inicio", "fecha_inicio"), ("Fin", "fecha_fin"), ("Estado", "estado"))


class PeriodoAcademicoCreateView(InstitutoCreateView):
    model = PeriodoAcademico
    form_class = PeriodoAcademicoForm
    title = "Nuevo periodo"
    success_url = reverse_lazy("matricula:periodo_list")
    cancel_url = reverse_lazy("matricula:periodo_list")


class PeriodoAcademicoUpdateView(InstitutoUpdateView):
    model = PeriodoAcademico
    form_class = PeriodoAcademicoForm
    title = "Editar periodo"
    success_url = reverse_lazy("matricula:periodo_list")
    cancel_url = reverse_lazy("matricula:periodo_list")


class CursoListView(InstitutoListView):
    model = Curso
    title = "Cursos"
    create_url_name = "matricula:curso_nuevo"
    columns = (("Nombre", "nombre"), ("Grado", "grado"), ("Carrera", "carrera"), ("Universidad", "universidad"), ("Activo", "activo"))


class CursoCreateView(InstitutoCreateView):
    model = Curso
    form_class = CursoForm
    title = "Nuevo curso"
    success_url = reverse_lazy("matricula:curso_list")


class CursoUpdateView(InstitutoUpdateView):
    model = Curso
    form_class = CursoForm
    title = "Editar curso"
    success_url = reverse_lazy("matricula:curso_list")


class AulaListView(InstitutoListView):
    model = Aula
    title = "Aulas"
    create_url_name = "matricula:aula_nueva"
    columns = (("Nombre", "nombre"), ("Seccion", "seccion"), ("Jornada", "jornada"), ("Horario", "horario"), ("Capacidad", "capacidad"))

    def get_queryset(self):
        return super().get_queryset().select_related("periodo_academico", "empresa")


class AulaCreateView(InstitutoCreateView):
    model = Aula
    form_class = AulaForm
    title = "Nueva aula"
    success_url = reverse_lazy("matricula:aula_list")
    cancel_url = reverse_lazy("matricula:aula_list")


class AulaUpdateView(InstitutoUpdateView):
    model = Aula
    form_class = AulaForm
    title = "Editar aula"
    success_url = reverse_lazy("matricula:aula_list")
    cancel_url = reverse_lazy("matricula:aula_list")


class FichaInscripcionListView(InstitutoListView):
    model = FichaInscripcion
    title = "Fichas de inscripcion"
    create_url_name = "matricula:matricula_proceso"
    create_label = "Matricular"
    update_url_name = "matricula:ficha_editar"
    columns = (
        ("Numero", "numero"),
        ("Fecha", "fecha"),
        ("Estudiante", "estudiante"),
        ("Representante", "representante"),
        ("Curso", "curso"),
        ("Aula", "aula"),
        ("Restante", "saldo"),
        ("Estado", "estado"),
    )

    def get_queryset(self):
        queryset = super().get_queryset().select_related("estudiante", "representante", "curso", "aula", "periodo_academico")
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(numero__icontains=q)
                | Q(estudiante__nombre__icontains=q)
                | Q(estudiante__identificacion__icontains=q)
                | Q(representante__nombre__icontains=q)
            )
        return queryset


class FichaInscripcionCreateView(InstitutoCreateView):
    model = FichaInscripcion
    form_class = FichaInscripcionForm
    title = "Nueva ficha de inscripcion"
    success_url = reverse_lazy("matricula:ficha_list")
    cancel_url = reverse_lazy("matricula:ficha_list")

    def get(self, request, *args, **kwargs):
        return redirect("matricula:matricula_proceso")

    def post(self, request, *args, **kwargs):
        return redirect("matricula:matricula_proceso")


class FichaInscripcionUpdateView(InstitutoUpdateView):
    model = FichaInscripcion
    form_class = FichaInscripcionForm
    title = "Editar ficha de inscripcion"
    cancel_url = reverse_lazy("matricula:ficha_list")

    def get_success_url(self):
        if self.request.POST.get("_after_save") == "print":
            return reverse("matricula:ficha_pdf", kwargs={"pk": self.object.pk})
        if self.request.POST.get("_after_save") == "documents":
            return reverse("matricula:ficha_documentos", kwargs={"pk": self.object.pk})
        return reverse("matricula:ficha_editar", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_actions"] = [
            {
                "label": "Ver documentos",
                "url": reverse("matricula:ficha_documentos", kwargs={"pk": self.object.pk}),
                "class": "btn-outline-primary",
            },
            {
                "label": "Imprimir ficha",
                "url": reverse("matricula:ficha_pdf", kwargs={"pk": self.object.pk}),
                "class": "btn-primary",
                "target": "_blank",
            },
        ]
        context["submit_actions"] = [
            {
                "label": "Guardar y ver documentos",
                "name": "_after_save",
                "value": "documents",
                "class": "btn-outline-primary",
            },
            {
                "label": "Guardar e imprimir ficha",
                "name": "_after_save",
                "value": "print",
                "class": "btn-outline-primary",
            },
        ]
        return context


class MatriculaProcesoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "matricula/proceso_form.html"
    permission_required = "matricula.add_fichainscripcion"
    session_key = "matricula_proceso"
    steps = (
        ("estudiante", "Estudiante", MatriculaEstudianteForm),
        ("representante", "Representante", MatriculaRepresentanteForm),
        ("matricula", "Matricula", MatriculaDatosForm),
        ("convenio", "Convenio de pago", MatriculaConvenioForm),
    )

    def dispatch(self, request, *args, **kwargs):
        if request.GET.get("reiniciar") == "1":
            request.session.pop(self.session_key, None)
            return redirect("matricula:matricula_proceso")
        return super().dispatch(request, *args, **kwargs)

    def get_empresa(self):
        return Empresa.objects.filter(activa=True).first()

    def get_initial(self, empresa):
        return {
            "numero": next_ficha_numero(empresa) if empresa else "",
            "fecha": timezone.localdate(),
            "fecha_inicio_cobro": timezone.localdate(),
            "forma_pago_convenio": "mensual",
        }

    def get_catalog_status(self, empresa):
        items = []
        if not empresa:
            return [
                {
                    "label": "Empresa activa",
                    "ready": False,
                    "url": reverse("core:empresa_list"),
                }
            ]

        active_payment = FormaPago.objects.filter(empresa=empresa, activo=True, es_pago=True).exists()
        items.extend(
            [
                {
                    "label": "Empresa activa",
                    "ready": True,
                    "url": reverse("core:empresa_list"),
                },
                {
                    "label": "Forma de pago inicial",
                    "ready": active_payment,
                    "url": reverse("cartera:forma_pago_list"),
                },
            ]
        )
        return items

    def get_display_from_model(self, model, value):
        if not value:
            return ""
        try:
            return str(model.objects.get(pk=value))
        except (model.DoesNotExist, TypeError, ValueError):
            return ""

    def build_summary(self, request, empresa):
        data = self.combined_querydict(self.get_session_data(request))
        valor_matricula = self.safe_decimal(data.get("valor_matricula"))
        valor_cuota = self.safe_decimal(data.get("valor_cuota"))
        numero_cuotas = self.safe_int(data.get("numero_cuotas"))
        abono = self.safe_decimal(data.get("abono"))
        total_cuotas = valor_cuota * numero_cuotas
        saldo = max(valor_matricula + total_cuotas - abono, Decimal("0"))
        return {
            "empresa": str(empresa) if empresa else "Pendiente",
            "estudiante": data.get("estudiante_nombre") or "Pendiente",
            "representante": data.get("representante_nombre") or "Pendiente",
            "numero": data.get("numero") or "Pendiente",
            "fecha": data.get("fecha") or "",
            "asignacion": "Pendiente",
            "valor_matricula": valor_matricula,
            "valor_cuota": valor_cuota,
            "numero_cuotas": numero_cuotas,
            "abono": abono,
            "saldo": saldo,
            "total_cuotas": total_cuotas,
            "total": saldo,
        }

    @staticmethod
    def safe_decimal(value):
        try:
            return Decimal(value or "0")
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @staticmethod
    def safe_int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def get_step_index(self, step):
        keys = [key for key, _, _ in self.steps]
        if step in keys:
            return keys.index(step)
        return 0

    def get_step(self, request):
        return self.steps[self.get_step_index(request.GET.get("paso"))]

    def get_session_data(self, request):
        return request.session.get(self.session_key, {})

    def get_saved_partner_form_kwargs(self, session_data):
        return {
            "estudiante_guardado_id": session_data.get("estudiante", {}).get("partner_id"),
            "representante_guardado_id": session_data.get("representante", {}).get("partner_id"),
        }

    def add_same_identification_error(self, form, session_data):
        estudiante_identificacion = (session_data.get("estudiante", {}).get("estudiante_identificacion") or "").strip()
        representante_identificacion = (form.cleaned_data.get("representante_identificacion") or "").strip()
        if (
            estudiante_identificacion
            and representante_identificacion
            and estudiante_identificacion.lower() == representante_identificacion.lower()
        ):
            form.add_error(
                "representante_identificacion",
                "La identificacion del representante no puede ser igual a la del estudiante.",
            )
            return True
        return False

    def get_initial_for_step(self, request, empresa, form_class):
        initial = {}
        initial.update(self.get_initial(empresa))
        for step_data in self.get_session_data(request).values():
            initial.update(step_data)
        today = timezone.localdate()
        if "fecha" in form_class.field_names:
            initial["fecha"] = today
        if "fecha_inicio_cobro" in form_class.field_names:
            saved_date = self.safe_date(initial.get("fecha_inicio_cobro"))
            if saved_date is None or saved_date < today:
                initial["fecha_inicio_cobro"] = today
        return {field: initial.get(field) for field in form_class.field_names if field in initial}

    @staticmethod
    def safe_date(value):
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value or ""))
        except ValueError:
            return None

    def get_context(self, request, form, step_key, step_label, empresa):
        step_index = self.get_step_index(step_key)
        step_items = []
        for index, (key, label, _) in enumerate(self.steps):
            if index < step_index:
                status = "done"
            elif index == step_index:
                status = "active"
            else:
                status = "pending"
            step_items.append({"key": key, "label": label, "number": index + 1, "status": status})
        catalog_status = self.get_catalog_status(empresa)
        return {
            "form": form,
            "title": "Matricular",
            "step_key": step_key,
            "step_label": step_label,
            "step_index": step_index,
            "step_number": step_index + 1,
            "step_items": step_items,
            "is_first_step": step_index == 0,
            "is_last_step": step_index == len(self.steps) - 1,
            "back_step": self.steps[step_index - 1][0] if step_index else "",
            "catalog_status": catalog_status,
            "catalog_ready": all(item["ready"] for item in catalog_status),
            "process_summary": self.build_summary(request, empresa),
        }

    def get(self, request):
        empresa = self.get_empresa()
        step_key, step_label, form_class = self.get_step(request)
        session_data = self.get_session_data(request)
        form = form_class(
            empresa=empresa,
            initial=self.get_initial_for_step(request, empresa, form_class),
            **self.get_saved_partner_form_kwargs(session_data),
        )
        return render(request, self.template_name, self.get_context(request, form, step_key, step_label, empresa))

    @transaction.atomic
    def post(self, request):
        empresa = self.get_empresa()
        step_key, step_label, form_class = self.get_step(request)
        session_data = self.get_session_data(request)
        form = form_class(
            request.POST,
            empresa=empresa,
            initial=self.get_initial_for_step(request, empresa, form_class),
            **self.get_saved_partner_form_kwargs(session_data),
        )
        if not empresa:
            form.add_error(None, "Debe existir una empresa activa para registrar matriculas.")
        if not form.is_valid():
            return render(request, self.template_name, self.get_context(request, form, step_key, step_label, empresa))
        if step_key == "representante" and self.add_same_identification_error(form, session_data):
            return render(request, self.template_name, self.get_context(request, form, step_key, step_label, empresa))
        if step_key == "matricula":
            form.cleaned_data["fecha"] = timezone.localdate()

        session_data[step_key] = self.serialize_step(form)
        if step_key == "estudiante":
            session_data[step_key]["partner_id"] = str(self.guardar_estudiante(form.cleaned_data, empresa).pk)
        elif step_key == "representante":
            session_data[step_key]["partner_id"] = str(self.guardar_representante(form.cleaned_data, empresa).pk)
        request.session[self.session_key] = session_data
        request.session.modified = True

        step_index = self.get_step_index(step_key)
        if step_index < len(self.steps) - 1:
            next_step = self.steps[step_index + 1][0]
            return redirect(f"{reverse_lazy('matricula:matricula_proceso')}?paso={next_step}")

        full_form = MatriculaProcesoForm(
            self.combined_querydict(session_data),
            empresa=empresa,
            initial=self.get_initial(empresa),
            **self.get_saved_partner_form_kwargs(session_data),
        )
        if not full_form.is_valid():
            messages.error(request, "Revise los datos de la matricula antes de confirmar.")
            return redirect("matricula:matricula_proceso")

        ficha = self.crear_matricula(full_form.cleaned_data, empresa, request.user, session_data)
        request.session.pop(self.session_key, None)
        messages.success(request, "Matricula, plan de pago y cuotas generados correctamente.")
        return redirect("matricula:ficha_documentos", pk=ficha.pk)

    def serialize_step(self, form):
        data = {}
        for name, field in form.fields.items():
            value = form.cleaned_data.get(name)
            if getattr(field.widget, "input_type", "") == "checkbox":
                data[name] = "on" if value else ""
            elif hasattr(value, "pk"):
                data[name] = str(value.pk)
            elif hasattr(value, "isoformat"):
                data[name] = value.isoformat()
            elif value is None:
                data[name] = ""
            else:
                data[name] = str(value)
        return data

    def get_tipo_identificacion(self):
        tipo_identificacion = TipoIdentificacion.objects.filter(activo=True).first()
        if not tipo_identificacion:
            tipo_identificacion = TipoIdentificacion.objects.create(nombre="Cedula", codigo="05", activo=True)
        return tipo_identificacion

    def guardar_estudiante(self, data, empresa):
        if data.get("estudiante_modo") == "seleccionar" and data.get("estudiante_partner"):
            partner = data["estudiante_partner"]
            if not partner.es_estudiante or not partner.activo:
                partner.es_estudiante = True
                partner.activo = True
                partner.save(update_fields=["es_estudiante", "activo"])
            return partner
        return self.guardar_partner(
            empresa=empresa,
            tipo_identificacion=self.get_tipo_identificacion(),
            identificacion=data["estudiante_identificacion"],
            nombre=data["estudiante_nombre"],
            email=data["estudiante_email"],
            telefono_celular=data["estudiante_telefono"],
            fecha_nacimiento=data["estudiante_fecha_nacimiento"],
            es_estudiante=True,
        )

    def guardar_representante(self, data, empresa):
        if data.get("representante_modo") == "seleccionar" and data.get("representante_partner"):
            partner = data["representante_partner"]
            update_fields = []
            if not partner.es_cliente:
                partner.es_cliente = True
                update_fields.append("es_cliente")
            if not partner.es_representante:
                partner.es_representante = True
                update_fields.append("es_representante")
            if not partner.activo:
                partner.activo = True
                update_fields.append("activo")
            if update_fields:
                partner.save(update_fields=update_fields)
            self.guardar_conyuge_partner(partner, data)
            return partner
        partner = self.guardar_partner(
            empresa=empresa,
            tipo_identificacion=self.get_tipo_identificacion(),
            identificacion=data["representante_identificacion"],
            nombre=data["representante_nombre"],
            email=data["representante_email"],
            telefono=data["representante_telefono"],
            telefono_celular=data["representante_celular"],
            direccion=data["representante_direccion"],
            ocupacion=data["representante_ocupacion"],
            es_cliente=True,
            es_representante=True,
        )
        self.guardar_conyuge_partner(partner, data)
        return partner

    def guardar_conyuge_partner(self, partner, data):
        nombre_conyuge = data.get("nombre_conyuge") or ""
        ocupacion_conyuge = data.get("ocupacion_conyuge") or ""
        if not nombre_conyuge and not ocupacion_conyuge:
            return
        tags = partner.tags or {}
        tags["nombre_conyuge"] = nombre_conyuge
        tags["ocupacion_conyuge"] = ocupacion_conyuge
        partner.tags = tags
        partner.save(update_fields=["tags"])

    def combined_querydict(self, session_data):
        data = QueryDict("", mutable=True)
        for _, _, form_class in self.steps:
            step_data = session_data.get(form_class.__name__.replace("Matricula", "").replace("Form", "").lower(), {})
            for key, value in step_data.items():
                if value != "":
                    data[key] = value
        # Keep compatibility with the explicit step keys used in the session.
        for step_key, step_data in session_data.items():
            for key, value in step_data.items():
                if value != "":
                    data[key] = value
        return data

    def crear_matricula(self, data, empresa, user, session_data):
        data["fecha"] = timezone.localdate()
        estudiante_id = session_data.get("estudiante", {}).get("partner_id")
        representante_id = session_data.get("representante", {}).get("partner_id")
        estudiante = get_object_or_404(Partner, pk=estudiante_id) if estudiante_id else self.guardar_estudiante(data, empresa)
        representante = (
            get_object_or_404(Partner, pk=representante_id)
            if representante_id
            else self.guardar_representante(data, empresa)
        )
        relacion, _ = PartnerPartner.objects.get_or_create(
            partner_a=estudiante,
            partner_b=representante,
            relacion="representante",
            defaults={
                "principal": True,
                "contacto_emergencia": True,
                "activo": True,
                "usuario_updated": user,
            },
        )
        relacion_updates = []
        for field in ["principal", "contacto_emergencia", "activo"]:
            if not getattr(relacion, field):
                setattr(relacion, field, True)
                relacion_updates.append(field)
        if relacion_updates:
            relacion.usuario_updated = user
            relacion_updates.append("usuario_updated")
            relacion.save(update_fields=relacion_updates)

        saldo = data["saldo_calculado"]
        valor_matricula = data["valor_matricula"]
        total_curso = data["valor_total_curso"]
        total = total_curso + valor_matricula
        fecha_proximo_pago, valor_proximo_pago = self.proximo_pago_pendiente(data)
        ficha = FichaInscripcion.objects.create(
            empresa=empresa,
            numero=data["numero"] or next_ficha_numero(empresa),
            fecha=data["fecha"],
            periodo_academico=data.get("periodo_academico"),
            curso=data.get("curso"),
            aula=data.get("aula"),
            cliente=representante,
            estudiante=estudiante,
            representante=representante,
            edad=data["edad"],
            colegio=data["colegio"],
            curso_grado=data.get("curso_grado"),
            nota_grado=data.get("nota_grado"),
            carrera=data.get("carrera"),
            universidad=data.get("universidad"),
            nombre_conyuge=data.get("nombre_conyuge"),
            ocupacion_conyuge=data.get("ocupacion_conyuge"),
            correo_estudiante=data["estudiante_email"],
            correo_representante=data["representante_email"],
            horario=data.get("horario") or (data["aula"].horario if data.get("aula") else ""),
            hora=data.get("hora") or (data["aula"].hora if data.get("aula") else ""),
            duracion=data.get("duracion") or (data["aula"].duracion if data.get("aula") else ""),
            forma_pago_convenio=data["forma_pago_convenio"],
            fecha_proximo_pago=fecha_proximo_pago,
            valor_proximo_pago=valor_proximo_pago,
            valor_total_curso=total_curso,
            valor_matricula=valor_matricula,
            descuento=Decimal("0.00"),
            abono=data["abono"],
            saldo=saldo,
            promo=data["promo"],
            autorizacion_imagen=data["autorizacion_imagen"],
            acepta_garantia=data["acepta_garantia"],
            acepta_no_devolucion=data["acepta_no_devolucion"],
            estado="activa",
            observacion=data["observacion"],
            usuario_updated=user,
        )
        if ficha.aula_id:
            AulaHistorial.objects.create(
                ficha_inscripcion=ficha,
                aula_destino=ficha.aula,
                motivo="Asignacion inicial por matricula",
                usuario=user,
            )
        plan = PlanPago.objects.create(
            empresa=empresa,
            ficha_inscripcion=ficha,
            valor_total=total,
            valor_matricula=valor_matricula,
            descuento=Decimal("0.00"),
            abono=data["abono"],
            saldo=saldo,
            estado="activo",
            observacion=data["observacion"],
            usuario_updated=user,
        )
        self.crear_cuotas_y_abono(plan, data, empresa, user)
        return ficha

    def guardar_partner(self, **kwargs):
        identificacion = kwargs.pop("identificacion")
        flags = {
            "es_cliente": kwargs.pop("es_cliente", False),
            "es_estudiante": kwargs.pop("es_estudiante", False),
            "es_representante": kwargs.pop("es_representante", False),
            "es_docente": kwargs.pop("es_docente", False),
        }
        partner, _ = Partner.objects.get_or_create(
            identificacion=identificacion,
            defaults={
                "tipo_identificacion": kwargs["tipo_identificacion"],
                "empresa": kwargs["empresa"],
                "nombre": kwargs["nombre"],
                **flags,
            },
        )
        for field, value in kwargs.items():
            if value not in (None, ""):
                setattr(partner, field, value)
        for field, value in flags.items():
            setattr(partner, field, getattr(partner, field) or value)
        partner.activo = True
        partner.save()
        return partner

    def fecha_cuota(self, data, indice):
        if data["forma_pago_convenio"] == "quincenal":
            return data["fecha_inicio_cobro"] + timedelta(days=15 * (indice - 1))
        return add_months(data["fecha_inicio_cobro"], indice - 1)

    def proximo_pago_pendiente(self, data):
        restante_abono = data["abono"]
        valor_matricula = data["valor_matricula"]
        if valor_matricula > 0:
            saldo_matricula = max(valor_matricula - restante_abono, Decimal("0.00"))
            if saldo_matricula > 0:
                return data["fecha"], saldo_matricula
            restante_abono = max(restante_abono - valor_matricula, Decimal("0.00"))

        for indice in range(1, data["numero_cuotas"] + 1):
            valor_cuota = data["valor_cuota"]
            saldo_cuota = max(valor_cuota - restante_abono, Decimal("0.00"))
            if saldo_cuota > 0:
                return self.fecha_cuota(data, indice), saldo_cuota
            restante_abono = max(restante_abono - valor_cuota, Decimal("0.00"))
        return data["fecha_inicio_cobro"], Decimal("0.00")

    def aplicar_pago_inicial(self, cuota, monto_disponible, data, empresa, user, comentario):
        if monto_disponible <= 0:
            return monto_disponible
        valor_pago = min(cuota.saldo(), monto_disponible)
        if valor_pago <= 0:
            return monto_disponible

        cuota.valor_pagado += valor_pago
        cuota.estado = "pagada" if cuota.valor_pagado >= cuota.valor else "parcial"
        cuota.usuario_updated = user
        cuota.save(update_fields=["valor_pagado", "estado", "usuario_updated", "updated"])
        Pago.objects.create(
            empresa=empresa,
            cuota=cuota,
            forma_pago=data["forma_pago_abono"],
            fecha_registro=timezone.now(),
            valor=valor_pago,
            numero_documento=data["numero_documento_abono"],
            comentario=comentario,
            usuario=user,
            usuario_updated=user,
        )
        return monto_disponible - valor_pago

    def crear_cuotas_y_abono(self, plan, data, empresa, user):
        abono_disponible = data["abono"]
        if data["valor_matricula"] > 0:
            cuota_matricula = Cuota.objects.create(
                plan_pago=plan,
                numero=Cuota.NUMERO_MATRICULA,
                fecha_pago_debito=data["fecha"],
                valor=data["valor_matricula"],
                valor_pagado=Decimal("0.00"),
                numero_recibo_factura_deposito=data["numero_documento_abono"],
                observacion="Matricula",
                estado="pendiente",
                prioridad="normal",
                usuario_updated=user,
            )
            abono_disponible = self.aplicar_pago_inicial(
                cuota_matricula,
                abono_disponible,
                data,
                empresa,
                user,
                "Pago de matricula",
            )
        for indice in range(1, data["numero_cuotas"] + 1):
            valor = data["valor_cuota"]
            cuota = Cuota.objects.create(
                plan_pago=plan,
                numero=indice,
                fecha_pago_debito=self.fecha_cuota(data, indice),
                valor=valor,
                valor_pagado=Decimal("0.00"),
                estado="pendiente" if valor else "pagada",
                prioridad="normal",
                usuario_updated=user,
            )
            abono_disponible = self.aplicar_pago_inicial(
                cuota,
                abono_disponible,
                data,
                empresa,
                user,
                f"Abono inicial aplicado a {cuota.etiqueta()}",
            )


def get_ficha_documento(pk):
    return get_object_or_404(
        FichaInscripcion.objects.select_related(
            "empresa",
            "cliente",
            "estudiante",
            "representante",
            "curso",
            "aula",
            "plan_pago",
        ),
        pk=pk,
    )


@login_required
@permission_required("matricula.view_fichainscripcion", raise_exception=True)
def ficha_documentos(request, pk):
    ficha = get_ficha_documento(pk)
    cuotas = ficha.plan_pago.cuotas.all() if hasattr(ficha, "plan_pago") else []
    return render(
        request,
        "matricula/ficha_documentos.html",
        {"ficha": ficha, "cuotas": cuotas, "template_path": TEMPLATE_PATH},
    )


@login_required
@permission_required("matricula.view_fichainscripcion", raise_exception=True)
def ficha_odt(request, pk):
    return ficha_documento_descarga(pk, "odt")


@login_required
@permission_required("matricula.view_fichainscripcion", raise_exception=True)
def ficha_pdf(request, pk):
    return ficha_documento_descarga(pk, "pdf")


@login_required
@permission_required("matricula.view_fichainscripcion", raise_exception=True)
def representante_prefill(request, pk):
    representante = get_object_or_404(Partner, pk=pk, activo=True, es_representante=True)
    conyuge = representante_conyuge_data(representante)
    return JsonResponse(
        {
            "identificacion": representante.identificacion,
            "nombre": representante.nombre,
            "telefono": representante.telefono or "",
            "celular": representante.telefono_celular or "",
            "email": representante.email or "",
            "ocupacion": representante.ocupacion or "",
            "direccion": representante.direccion or "",
            "nombre_conyuge": conyuge["nombre_conyuge"],
            "ocupacion_conyuge": conyuge["ocupacion_conyuge"],
        }
    )


def ficha_documento_descarga(pk, extension):
    ficha = get_object_or_404(
        FichaInscripcion.objects.select_related(
            "empresa",
            "cliente",
            "estudiante",
            "representante",
            "curso",
            "aula",
            "plan_pago",
        ),
        pk=pk,
    )
    temp_dir, path = build_document_response_file(ficha, extension)
    try:
        payload = path.read_bytes()
    finally:
        temp_dir.cleanup()
    content_type = "application/vnd.oasis.opendocument.text" if extension == "odt" else "application/pdf"
    response = HttpResponse(payload, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="matricula_{ficha.numero}.{extension}"'
    return response
