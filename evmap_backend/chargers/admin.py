from django.contrib import admin

from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector


# Register your models here.
class ChargepointInline(admin.StackedInline):
    model = Chargepoint


class ConnectorInline(admin.StackedInline):
    model = Connector


class ChargingSiteAdmin(admin.ModelAdmin):
    list_display = ["name", "data_source", "operator"]
    list_filter = ["data_source", "operator"]
    inlines = [ChargepointInline]


class ChargepointAdmin(admin.ModelAdmin):
    list_display = ["evseid"]
    inlines = [ConnectorInline]


class ConnectorAdmin(admin.ModelAdmin):
    list_display = [
        "chargepoint__site__operator",
        "chargepoint__evseid",
        "connector_type",
        "max_power",
    ]
    list_filter = ["connector_type", "chargepoint__site__operator"]


# Register your models here.
admin.site.register(ChargingSite, ChargingSiteAdmin)
admin.site.register(Chargepoint, ChargepointAdmin)
admin.site.register(Connector, ConnectorAdmin)
