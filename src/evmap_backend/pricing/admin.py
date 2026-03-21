from django.contrib import admin
from django.db.models import Count

from evmap_backend.pricing.models import NetworkTariffAssignment, PriceComponent, Tariff


class PriceComponentInline(admin.StackedInline):
    model = PriceComponent
    extra = 1


class NetworkTariffAssignmentInline(admin.StackedInline):
    model = NetworkTariffAssignment
    max_num = 1
    extra = 0
    raw_id_fields = ["network"]


class TariffAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "data_source",
        "currency",
        "is_adhoc",
        "pricing_summary",
        "chargepoints_count",
    ]
    list_filter = ["data_source", "is_adhoc", "currency"]
    search_fields = ["name", "id_from_source", "description"]
    inlines = [PriceComponentInline, NetworkTariffAssignmentInline]
    raw_id_fields = ["chargepoints"]

    @admin.display(description="Pricing")
    def pricing_summary(self, obj):
        components = list(obj.price_components.all())
        if not components:
            return "—"
        return " + ".join(str(pc) for pc in components)

    @admin.display(description="Chargepoints", ordering="chargepoints_count")
    def chargepoints_count(self, obj):
        return obj.chargepoints_count

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("price_components")
            .annotate(chargepoints_count=Count("chargepoints"))
        )


class PriceComponentAdmin(admin.ModelAdmin):
    list_display = ["tariff", "type", "price"]
    list_filter = ["type"]
    raw_id_fields = ["tariff"]


class NetworkTariffAssignmentAdmin(admin.ModelAdmin):
    list_display = ["tariff", "network", "is_dc", "min_power", "max_power"]
    list_filter = ["is_dc"]
    raw_id_fields = ["tariff", "network"]


admin.site.register(Tariff, TariffAdmin)
admin.site.register(PriceComponent, PriceComponentAdmin)
admin.site.register(NetworkTariffAssignment, NetworkTariffAssignmentAdmin)
