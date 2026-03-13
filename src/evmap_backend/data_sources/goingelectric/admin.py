from django.contrib import admin
from django.db.models import Count

from evmap_backend.data_sources.goingelectric.models import (
    GoingElectricChargeLocation,
    GoingElectricChargepoint,
    GoingElectricNetwork,
)


class GoingElectricChargepointInline(admin.StackedInline):
    model = GoingElectricChargepoint


class GoingElectricNetworkAdmin(admin.ModelAdmin):
    list_display = ["name", "chargelocations_count"]
    filter_horizontal = ["mapped_networks"]

    @admin.display(ordering="-chargelocations__count")
    def chargelocations_count(self, obj):
        return obj.chargelocations__count

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(Count("chargelocations"))
        return queryset


class GoingElectricChargeLocationAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "network",
        "id",
        "address_country",
        "matched_site",
        "match_confidence",
    ]
    list_filter = ["network", "address_country"]
    raw_id_fields = ["matched_site"]
    readonly_fields = ["match_confidence"]
    inlines = [GoingElectricChargepointInline]


class GoingElectricChargepointAdmin(admin.ModelAdmin):
    list_display = ["chargelocation__name", "type", "power", "count"]
    list_filter = ["type", "power"]


# Register your models here.
admin.site.register(GoingElectricChargeLocation, GoingElectricChargeLocationAdmin)
admin.site.register(GoingElectricChargepoint, GoingElectricChargepointAdmin)
admin.site.register(GoingElectricNetwork, GoingElectricNetworkAdmin)
