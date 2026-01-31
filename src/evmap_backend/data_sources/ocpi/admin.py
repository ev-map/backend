from django.contrib import admin

from evmap_backend.data_sources.ocpi.models import OcpiConnection
from evmap_backend.data_sources.registry import get_data_source


class OcpiCredentialsAdmin(admin.ModelAdmin):
    readonly_fields = [
        "token_b",
        "token_c",
        "version",
        "country_code",
        "party_id",
        "locations_url",
        "tariffs_url",
    ]
    list_display = ["data_source", "party_id", "url"]

    def get_readonly_fields(self, request, obj: OcpiConnection = None):
        readonly = super().get_readonly_fields(request, obj)
        data_source = get_data_source(obj.data_source)
        if not data_source.is_credentials_sender:
            return ["token_a", "url"] + readonly
        else:
            return readonly


# Register your models here.
admin.site.register(OcpiConnection, OcpiCredentialsAdmin)
