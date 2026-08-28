from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.models import Empresa


class InstitutoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = "web/object_list.html"
    paginate_by = 20
    title = ""
    create_url_name = None
    create_label = "Nuevo"
    update_url_name = None
    columns = ()

    def get_permission_required(self):
        opts = self.model._meta
        return (f"{opts.app_label}.view_{opts.model_name}",)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["create_url_name"] = self.create_url_name if self.can_create_object() else None
        context["create_label"] = self.create_label
        context["update_url_name"] = self.get_update_url_name()
        context["columns"] = self.columns
        context["object_rows"] = [self.get_row(obj) for obj in context["object_list"]]
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        context["pagination_query"] = query_params.urlencode()
        return context

    def get_row(self, obj):
        primary_url = self.get_primary_url(obj)
        update_url = self.get_update_url(obj)
        return {
            "object": obj,
            "primary_url": primary_url,
            "update_url": update_url,
            "action_label": self.get_action_label(obj),
            "values": [
                {
                    "value": self.get_column_value(obj, attr),
                    "is_primary": index == 0 and bool(primary_url),
                    "url": primary_url if index == 0 else "",
                    "kind": self.get_column_kind(attr),
                }
                for index, (_, attr) in enumerate(self.columns)
            ],
        }

    def can_create_object(self):
        opts = self.model._meta
        return self.request.user.has_perm(f"{opts.app_label}.add_{opts.model_name}")

    def can_update_object(self, obj):
        opts = self.model._meta
        return self.request.user.has_perm(f"{opts.app_label}.change_{opts.model_name}")

    def get_action_label(self, obj):
        return ""

    def get_primary_url(self, obj):
        if not self.can_update_object(obj):
            return ""
        return self.get_update_url(obj)

    def get_update_url_name(self):
        if self.update_url_name:
            return self.update_url_name
        if self.create_url_name:
            return self.create_url_name.replace("_nuevo", "_editar").replace("_nueva", "_editar")
        return None

    def get_update_url(self, obj):
        if not self.can_update_object(obj):
            return ""
        url_name = self.get_update_url_name()
        if not url_name:
            return ""
        return reverse(url_name, kwargs={"pk": obj.pk})

    def get_column_value(self, obj, attr):
        display_method = getattr(obj, f"get_{attr}_display", None)
        if callable(display_method):
            return display_method()
        value = obj
        for part in attr.split("."):
            value = getattr(value, part, "")
            if callable(value):
                value = value()
            if value is None:
                return ""
        return value

    def get_column_kind(self, attr):
        lowered = attr.lower()
        if lowered in {"estado", "activo", "is_active", "is_staff"} or lowered.endswith("estado"):
            return "status"
        return "text"


class InstitutoFormMixin(LoginRequiredMixin, PermissionRequiredMixin):
    template_name = "web/object_form.html"
    title = ""
    cancel_url = reverse_lazy("home")
    success_message = "Registro guardado correctamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["cancel_url"] = self.cancel_url
        context.setdefault("show_save_button", True)
        return context

    def get_initial(self):
        initial = super().get_initial()
        empresa = Empresa.objects.filter(activa=True).first()
        if empresa:
            initial.setdefault("empresa", empresa.pk)
        return initial

    def form_valid(self, form):
        if hasattr(form.instance, "usuario_updated"):
            form.instance.usuario_updated = self.request.user
        if hasattr(form.instance, "empresa_id") and not form.instance.empresa_id:
            empresa = Empresa.objects.filter(activa=True).first()
            if empresa:
                form.instance.empresa = empresa
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


class InstitutoCreateView(InstitutoFormMixin, CreateView):
    def get_permission_required(self):
        opts = self.model._meta
        return (f"{opts.app_label}.add_{opts.model_name}",)


class InstitutoUpdateView(InstitutoFormMixin, UpdateView):
    def get_permission_required(self):
        opts = self.model._meta
        return (f"{opts.app_label}.change_{opts.model_name}",)
