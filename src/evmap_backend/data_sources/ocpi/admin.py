from django.contrib import admin

from evmap_backend.data_sources.ocpi.models import OcpiConnection


class OcpiCredentialsAdmin(admin.ModelAdmin):
    readonly_fields = ["token_a", "token_b", "token_c"]
    list_display = ["data_source", "party_id", "url"]


# Register your models here.
admin.site.register(OcpiConnection, OcpiCredentialsAdmin)
