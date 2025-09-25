from django.contrib import admin

from evmap_backend.aggregator.models import EVSE, ChargeLocation, Connector


class EVSEInline(admin.StackedInline):
    model = EVSE


class ConnectorInline(admin.StackedInline):
    model = Connector


class ChargeLocationAdmin(admin.ModelAdmin):
    list_display = ["name", "network"]
    list_filter = ["network"]
    inlines = [EVSEInline]


class EVSEAdmin(admin.ModelAdmin):
    list_display = ["chargelocation__name", "evse_id"]
    inlines = [ConnectorInline]


class ConnectorAdmin(admin.ModelAdmin):
    list_display = ["evse__chargelocation__name", "evse__evse_id", "type", "power"]


# Register your models here.
admin.site.register(ChargeLocation, ChargeLocationAdmin)
admin.site.register(EVSE, EVSEAdmin)
admin.site.register(Connector, ConnectorAdmin)
