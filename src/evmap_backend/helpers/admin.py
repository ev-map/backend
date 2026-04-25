from django.contrib import admin


class SimpleDALFFilter(admin.SimpleListFilter):
    template = "admin/filter/django_admin_list_filter.html"

    def __init__(self, request, params, model, model_admin):
        super().__init__(request, params, model, model_admin)
        self.custom_template_params = {
            "app_label": model._meta.app_label,  # noqa: SLF001
            "model_name": model._meta.model_name,  # noqa: SLF001
            "field_name": self.parameter_name,
            "lookup_kwarg": self.parameter_name,
        }

    def choices(self, changelist):
        yield from super().choices(changelist)
        yield {
            **self.custom_template_params,
        }
