from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from evmap_backend.chargers.fields import format_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector, Network


# Register your models here.
class ChargepointInline(admin.StackedInline):
    model = Chargepoint
    show_change_link = True


class ConnectorInline(admin.StackedInline):
    model = Connector
    show_change_link = True


class ChargingSiteAdmin(GISModelAdmin):
    list_display = ["name", "data_source", "network", "city", "country"]
    list_filter = ["data_source", "network", "country"]
    inlines = [ChargepointInline]


class ChargepointAdmin(admin.ModelAdmin):
    list_display = ["formatted_evseid"]
    inlines = [ConnectorInline]

    @admin.display(description="EVSEID")
    def formatted_evseid(self, obj):
        return format_evseid(obj.evseid)


class ConnectorAdmin(admin.ModelAdmin):
    list_display = [
        "chargepoint__site__operator",
        "chargepoint__evseid",
        "connector_type",
        "max_power",
    ]
    list_filter = ["connector_type", "chargepoint__site__operator"]


class NetworkAdmin(admin.ModelAdmin):
    list_display = ["name", "evse_operator_id"]


# Register your models here.
admin.site.register(ChargingSite, ChargingSiteAdmin)
admin.site.register(Chargepoint, ChargepointAdmin)
admin.site.register(Connector, ConnectorAdmin)
admin.site.register(Network, NetworkAdmin)
