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


# Register your models here.
admin.site.register(Datex2EnergyInfrastructureSite, Datex2EnergyInfrastructureSiteAdmin)
admin.site.register(Datex2RefillPoint, Datex2RefillPointAdmin)
