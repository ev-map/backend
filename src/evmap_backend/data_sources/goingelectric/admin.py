from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from evmap_backend.chargers.models import Network
from evmap_backend.data_sources.goingelectric.matching import suggest_network_mappings
from evmap_backend.data_sources.goingelectric.models import (
    GoingElectricChargeLocation,
    GoingElectricChargepoint,
    GoingElectricNetwork,
)


class GoingElectricChargepointInline(admin.StackedInline):
    model = GoingElectricChargepoint


class GoingElectricNetworkAdmin(admin.ModelAdmin):
    list_display = ["name", "chargelocations_count", "mapped_networks_display"]
    filter_horizontal = ["mapped_networks"]

    @admin.display(ordering="-chargelocations__count")
    def chargelocations_count(self, obj):
        return obj.chargelocations__count

    @admin.display(description="Mapped networks")
    def mapped_networks_display(self, obj):
        return ", ".join(str(n) for n in obj.mapped_networks.all()) or "—"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(Count("chargelocations")).order_by(
            "-chargelocations__count"
        )
        return queryset

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/add-suggested-mappings/",
                self.admin_site.admin_view(self.add_suggested_mappings_view),
                name="goingelectric_goingelectricnetwork_add_suggested_mappings",
            ),
        ]
        return custom + urls

    def add_suggested_mappings_view(self, request, pk):
        """POST-only view to add selected network mappings."""
        if request.method != "POST":
            return HttpResponseRedirect(
                reverse(
                    "admin:goingelectric_goingelectricnetwork_change",
                    args=[pk],
                )
            )

        ge_network = GoingElectricNetwork.objects.get(pk=pk)
        network_ids = request.POST.getlist("network_ids")
        for nid in network_ids:
            ge_network.mapped_networks.add(int(nid))
        self.message_user(
            request,
            f"Added {len(network_ids)} network mapping(s) to {ge_network}.",
        )
        changelist_url = reverse("admin:goingelectric_goingelectricnetwork_changelist")
        preserved_filters = request.POST.get("_changelist_filters", "")
        if preserved_filters:
            changelist_url = f"{changelist_url}?{preserved_filters}"
        return HttpResponseRedirect(changelist_url)

    def _get_suggestions(self, ge_network: GoingElectricNetwork):
        """Build the suggestions list for a GE network."""
        existing_ids = set(ge_network.mapped_networks.values_list("id", flat=True))

        suggestions_map = suggest_network_mappings(ge_network=ge_network)
        network_counts = suggestions_map.get(ge_network.id, {})

        networks = {
            n.id: n for n in Network.objects.filter(id__in=network_counts.keys())
        }

        suggestions = []
        for net_id, count in sorted(network_counts.items(), key=lambda x: -x[1]):
            net = networks.get(net_id)
            if net is None:
                continue
            suggestions.append(
                {
                    "network": net,
                    "count": count,
                    "already_mapped": net_id in existing_ids,
                }
            )
        return suggestions

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        ge_network = GoingElectricNetwork.objects.prefetch_related(
            "mapped_networks"
        ).get(pk=object_id)
        extra_context["suggestions"] = self._get_suggestions(ge_network)
        extra_context["add_mappings_url"] = reverse(
            "admin:goingelectric_goingelectricnetwork_add_suggested_mappings",
            args=[object_id],
        )
        extra_context["preserved_filters"] = request.GET.get("_changelist_filters", "")
        return super().change_view(request, object_id, form_url, extra_context)


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
