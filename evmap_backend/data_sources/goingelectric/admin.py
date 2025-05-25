from django.contrib import admin

from evmap_backend.data_sources.goingelectric.models import (
    GoingElectricChargeLocation,
    GoingElectricChargepoint,
)


class GoingElectricChargepointInline(admin.StackedInline):
    model = GoingElectricChargepoint


class GoingElectricChargeLocationAdmin(admin.ModelAdmin):
    list_display = ["name", "network", "id", "address_country"]
    list_filter = ["network", "address_country"]
    inlines = [GoingElectricChargepointInline]


class GoingElectricChargepointAdmin(admin.ModelAdmin):
    list_display = ["chargelocation__name", "type", "power", "count"]
    list_filter = ["type", "power"]


# Register your models here.
admin.site.register(GoingElectricChargeLocation, GoingElectricChargeLocationAdmin)
admin.site.register(GoingElectricChargepoint, GoingElectricChargepointAdmin)
