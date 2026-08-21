from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.models import Empresa


class InstitutoListView(LoginRequiredMixin, ListView):
    template_name = "web/object_list.html"
    paginate_by = 20
    title = ""
    create_url_name = None
    update_url_name = None
    columns = ()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["create_url_name"] = self.create_url_name
        context["update_url_name"] = self.get_update_url_name()
        context["columns"] = self.columns
        context["object_rows"] = [self.get_row(obj) for obj in context["object_list"]]
        return context

    def get_row(self, obj):
        return {
            "object": obj,
            "update_url": self.get_update_url(obj),
            "values": [self.get_column_value(obj, attr) for _, attr in self.columns],
        }

    def get_update_url_name(self):
        if self.update_url_name:
            return self.update_url_name
        if self.create_url_name:
            return self.create_url_name.replace("_nuevo", "_editar").replace("_nueva", "_editar")
        return None

    def get_update_url(self, obj):
        url_name = self.get_update_url_name()
        if not url_name:
            return ""
        return reverse(url_name, kwargs={"pk": obj.pk})

    def get_column_value(self, obj, attr):
        value = obj
        for part in attr.split("."):
            value = getattr(value, part, "")
            if callable(value):
                value = value()
            if value is None:
                return ""
        return value


class InstitutoFormMixin(LoginRequiredMixin):
    template_name = "web/object_form.html"
    title = ""
    cancel_url = reverse_lazy("home")
    success_message = "Registro guardado correctamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["cancel_url"] = self.cancel_url
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
    pass


class InstitutoUpdateView(InstitutoFormMixin, UpdateView):
    pass
