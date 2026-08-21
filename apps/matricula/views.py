from calendar import monthrange
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Max, Q
from django.http import HttpResponse
from django.http import QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View

from apps.cartera.models import Cuota, Pago, PlanPago
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
)
from .models import Aula, Curso, FichaInscripcion, PeriodoAcademico
from .odt import TEMPLATE_PATH, build_document_response_file


def add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def next_ficha_numero(empresa):
    ultimo_id = FichaInscripcion.objects.filter(empresa=empresa).aggregate(Max("id"))["id__max"] or 0
    return str(ultimo_id + 1).zfill(7)


def monto_cuota(valor, numero_cuotas, indice):
    valor = Decimal(valor)
    base = (valor / numero_cuotas).quantize(Decimal("0.01"))
    if indice < numero_cuotas:
        return base
    return valor - (base * (numero_cuotas - 1))


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
    cancel_url = reverse_lazy("matricula:curso_list")


class CursoUpdateView(InstitutoUpdateView):
    model = Curso
    form_class = CursoForm
    title = "Editar curso"
    success_url = reverse_lazy("matricula:curso_list")
    cancel_url = reverse_lazy("matricula:curso_list")


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
    create_url_name = "matricula:ficha_nueva"
    columns = (
        ("Numero", "numero"),
        ("Fecha", "fecha"),
        ("Estudiante", "estudiante"),
        ("Representante", "representante"),
        ("Curso", "curso"),
        ("Saldo", "saldo"),
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


class MatriculaProcesoView(LoginRequiredMixin, View):
    template_name = "matricula/proceso_form.html"
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
        periodo = PeriodoAcademico.objects.filter(empresa=empresa, estado="activo", activo=True).first() if empresa else None
        return {
            "numero": next_ficha_numero(empresa) if empresa else "",
            "fecha": timezone.localdate(),
            "periodo_academico": periodo,
            "fecha_inicio_cobro": timezone.localdate(),
            "forma_pago_convenio": "mensual",
        }

    def get_step_index(self, step):
        keys = [key for key, _, _ in self.steps]
        if step in keys:
            return keys.index(step)
        return 0

    def get_step(self, request):
        return self.steps[self.get_step_index(request.GET.get("paso"))]

    def get_session_data(self, request):
        return request.session.get(self.session_key, {})

    def get_initial_for_step(self, request, empresa, form_class):
        initial = {}
        initial.update(self.get_initial(empresa))
        for step_data in self.get_session_data(request).values():
            initial.update(step_data)
        return {field: initial.get(field) for field in form_class.field_names if field in initial}

    def get_context(self, request, form, step_key, step_label):
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
        }

    def get(self, request):
        empresa = self.get_empresa()
        step_key, step_label, form_class = self.get_step(request)
        form = form_class(empresa=empresa, initial=self.get_initial_for_step(request, empresa, form_class))
        return render(request, self.template_name, self.get_context(request, form, step_key, step_label))

    @transaction.atomic
    def post(self, request):
        empresa = self.get_empresa()
        step_key, step_label, form_class = self.get_step(request)
        form = form_class(request.POST, empresa=empresa)
        if not empresa:
            form.add_error(None, "Debe existir una empresa activa para registrar matriculas.")
        if not form.is_valid():
            return render(request, self.template_name, self.get_context(request, form, step_key, step_label))

        session_data = self.get_session_data(request)
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

        full_form = MatriculaProcesoForm(self.combined_querydict(session_data), empresa=empresa)
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
            return data["estudiante_partner"]
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
            return data["representante_partner"]
        return self.guardar_partner(
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
        estudiante_id = session_data.get("estudiante", {}).get("partner_id")
        representante_id = session_data.get("representante", {}).get("partner_id")
        estudiante = get_object_or_404(Partner, pk=estudiante_id) if estudiante_id else self.guardar_estudiante(data, empresa)
        representante = (
            get_object_or_404(Partner, pk=representante_id)
            if representante_id
            else self.guardar_representante(data, empresa)
        )
        PartnerPartner.objects.get_or_create(
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

        total = data["valor_total_curso"] + data["valor_matricula"] - data["descuento"]
        saldo = total - data["abono"]
        ficha = FichaInscripcion.objects.create(
            empresa=empresa,
            numero=data["numero"] or next_ficha_numero(empresa),
            fecha=data["fecha"],
            periodo_academico=data["periodo_academico"],
            curso=data["curso"],
            aula=data["aula"],
            cliente=representante,
            estudiante=estudiante,
            representante=representante,
            edad=data["edad"],
            colegio=data["colegio"],
            curso_grado=data["curso_grado"],
            nota_grado=data["nota_grado"],
            carrera=data["carrera"],
            universidad=data["universidad"],
            nombre_conyuge=data["nombre_conyuge"],
            ocupacion_conyuge=data["ocupacion_conyuge"],
            correo_estudiante=data["estudiante_email"],
            correo_representante=data["representante_email"],
            horario=data["horario"] or (data["aula"].horario if data["aula"] else ""),
            hora=data["hora"] or (data["aula"].hora if data["aula"] else ""),
            duracion=data["duracion"] or (data["aula"].duracion if data["aula"] else ""),
            forma_pago_convenio=data["forma_pago_convenio"],
            fecha_proximo_pago=data["fecha_inicio_cobro"],
            valor_proximo_pago=monto_cuota(saldo, data["numero_cuotas"], 1) if saldo else Decimal("0.00"),
            valor_total_curso=data["valor_total_curso"],
            valor_matricula=data["valor_matricula"],
            descuento=data["descuento"],
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
        plan = PlanPago.objects.create(
            empresa=empresa,
            ficha_inscripcion=ficha,
            valor_total=total,
            valor_matricula=data["valor_matricula"],
            descuento=data["descuento"],
            abono=data["abono"],
            saldo=saldo,
            estado="activo",
            observacion=data["observacion"],
            usuario_updated=user,
        )
        self.crear_cuotas_y_abono(plan, data, empresa, user, saldo)
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

    def crear_cuotas_y_abono(self, plan, data, empresa, user, saldo):
        if data["abono"] > 0:
            cuota_abono = Cuota.objects.create(
                plan_pago=plan,
                numero=0,
                fecha_pago_debito=data["fecha"],
                valor=data["abono"],
                valor_pagado=data["abono"],
                numero_recibo_factura_deposito=data["numero_documento_abono"],
                observacion="Abono inicial",
                estado="pagada",
                prioridad="normal",
                usuario_updated=user,
            )
            Pago.objects.create(
                empresa=empresa,
                cuota=cuota_abono,
                forma_pago=data["forma_pago_abono"],
                fecha_registro=timezone.now(),
                valor=data["abono"],
                numero_documento=data["numero_documento_abono"],
                comentario="Abono inicial de matricula",
                usuario=user,
                usuario_updated=user,
            )
        if saldo <= 0:
            return
        for indice in range(1, data["numero_cuotas"] + 1):
            if data["forma_pago_convenio"] == "quincenal":
                fecha_cuota = data["fecha_inicio_cobro"] + timedelta(days=15 * (indice - 1))
            else:
                fecha_cuota = add_months(data["fecha_inicio_cobro"], indice - 1)
            valor = monto_cuota(saldo, data["numero_cuotas"], indice)
            Cuota.objects.create(
                plan_pago=plan,
                numero=indice,
                fecha_pago_debito=fecha_cuota,
                valor=valor,
                valor_pagado=Decimal("0.00"),
                estado="pendiente" if valor else "pagada",
                prioridad="normal",
                usuario_updated=user,
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
def ficha_documentos(request, pk):
    ficha = get_ficha_documento(pk)
    cuotas = ficha.plan_pago.cuotas.all() if hasattr(ficha, "plan_pago") else []
    return render(
        request,
        "matricula/ficha_documentos.html",
        {"ficha": ficha, "cuotas": cuotas, "template_path": TEMPLATE_PATH},
    )


@login_required
def ficha_odt(request, pk):
    return ficha_documento_descarga(pk, "odt")


@login_required
def ficha_pdf(request, pk):
    return ficha_documento_descarga(pk, "pdf")


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
