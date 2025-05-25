from django.contrib import admin

from evmap_backend.data_sources.datex2.models import (
    Datex2Connector,
    Datex2EnergyInfrastructureSite,
    Datex2RefillPoint,
)


class Datex2RefillPointInline(admin.StackedInline):
    model = Datex2RefillPoint


class Datex2ConnectorInline(admin.StackedInline):
    model = Datex2Connector


class Datex2EnergyInfrastructureSiteAdmin(admin.ModelAdmin):
    list_display = ["name", "operatorName"]
    list_filter = ["operatorName"]
    inlines = [Datex2RefillPointInline]


class Datex2RefillPointAdmin(admin.ModelAdmin):
    list_display = ["externalIdentifier"]
    inlines = [Datex2ConnectorInline]


class Datex2ConnectorAdmin(admin.ModelAdmin):
    list_display = [
        "refill_point__site__operatorName",
        "refill_point__externalIdentifier",
        "connector_type",
        "max_power",
    ]
    list_filter = ["connector_type", "refill_point__site__operatorName"]


# Register your models here.
admin.site.register(Datex2EnergyInfrastructureSite, Datex2EnergyInfrastructureSiteAdmin)
admin.site.register(Datex2RefillPoint, Datex2RefillPointAdmin)
admin.site.register(Datex2Connector, Datex2ConnectorAdmin)
