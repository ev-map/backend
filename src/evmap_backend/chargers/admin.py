from dalf.admin import (
    DALFChoicesField,
    DALFModelAdmin,
    DALFRelatedField,
)
from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.db.models import Count

from evmap_backend.chargers.fields import format_evse_operator_id, format_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector, Network


# Register your models here.
class ChargepointInline(admin.StackedInline):
    model = Chargepoint
    show_change_link = True


class ConnectorInline(admin.StackedInline):
    model = Connector
    show_change_link = True


class ChargingSiteAdmin(DALFModelAdmin, GISModelAdmin):
    list_display = ["name", "data_source", "network", "city", "country"]
    list_filter = [
        "data_source",
        ("network", DALFRelatedField),
        ("country", DALFChoicesField),
    ]
    inlines = [ChargepointInline]


class ChargepointAdmin(admin.ModelAdmin):
    list_display = ["formatted_evseid", "physical_reference"]
    inlines = [ConnectorInline]
    raw_id_fields = ["site"]
    search_fields = ["evseid"]
    search_help_text = "Search by EVSEID without separators"

    @admin.display(description="EVSEID")
    def formatted_evseid(self, obj):
        return format_evseid(obj.evseid) if obj.evseid else ""


class ConnectorAdmin(admin.ModelAdmin):
    list_select_related = ["chargepoint", "chargepoint__site"]
    list_display = [
        "chargepoint__site__operator",
        "chargepoint__evseid",
        "connector_type",
        "max_power",
    ]
    list_filter = ["connector_type", "chargepoint__site__operator"]
    autocomplete_fields = ["chargepoint"]


class NetworkAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "formatted_evse_operator_id",
        "chargingsites_count",
        "goingelectric_networks_display",
    ]
    search_fields = ["name", "evse_operator_id"]

    @admin.display(description="EVSE Operator ID")
    def formatted_evse_operator_id(self, obj):
        return (
            format_evse_operator_id(obj.evse_operator_id)
            if obj.evse_operator_id
            else ""
        )

    @admin.display(ordering="-chargingsites__count")
    def chargingsites_count(self, obj):
        return obj.chargingsites__count

    @admin.display(description="GoingElectric networks")
    def goingelectric_networks_display(self, obj):
        return ", ".join(str(n) for n in obj.goingelectric_networks.all()) or "—"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(Count("chargingsites")).order_by(
            "-chargingsites__count"
        )
        return queryset


# Register your models here.
admin.site.register(ChargingSite, ChargingSiteAdmin)
admin.site.register(Chargepoint, ChargepointAdmin)
admin.site.register(Connector, ConnectorAdmin)
admin.site.register(Network, NetworkAdmin)
